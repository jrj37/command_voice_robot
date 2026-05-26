/**
 * Capture du micro → PCM 16-bit mono 16 kHz envoyé en chunks via callback.
 * Utilise AudioWorklet pour resampler en JS, et un VAD simple basé sur l'énergie
 * pour déclencher un flush quand l'utilisateur arrête de parler.
 */

const TARGET_SAMPLE_RATE = 16000;
const SILENCE_THRESHOLD = 0.005;    // RMS en dessous duquel on considère silence
const SILENCE_DURATION_MS = 800;    // silence requis pour flush
const MIN_SPEECH_MS = 200;          // ignorer les bouts trop courts

export interface AudioRecorderEvents {
  onChunk: (pcm: ArrayBuffer) => void;
  onFlush: () => void;
  onLevel?: (rms: number) => void;
  onError?: (e: Error) => void;
}

export class AudioRecorder {
  private ctx: AudioContext | null = null;
  private stream: MediaStream | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private worklet: AudioWorkletNode | null = null;
  private events: AudioRecorderEvents;
  private speechStartedAt: number | null = null;
  private lastVoiceAt: number = 0;
  private pcmBuffer: Int16Array[] = [];

  constructor(events: AudioRecorderEvents) {
    this.events = events;
  }

  async start() {
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, noiseSuppression: true, echoCancellation: true },
      });
      this.ctx = new AudioContext();
      const inputSampleRate = this.ctx.sampleRate;

      // Inline AudioWorklet — pas de fichier séparé à servir
      const workletCode = `
        class CaptureProcessor extends AudioWorkletProcessor {
          process(inputs) {
            const ch = inputs[0]?.[0];
            if (ch) this.port.postMessage(ch);
            return true;
          }
        }
        registerProcessor('capture-processor', CaptureProcessor);
      `;
      const blob = new Blob([workletCode], { type: "application/javascript" });
      const url = URL.createObjectURL(blob);
      await this.ctx.audioWorklet.addModule(url);
      URL.revokeObjectURL(url);

      this.source = this.ctx.createMediaStreamSource(this.stream);
      this.worklet = new AudioWorkletNode(this.ctx, "capture-processor");
      this.source.connect(this.worklet);
      // Pas besoin de connecter à destination (pas de monitoring)

      const ratio = inputSampleRate / TARGET_SAMPLE_RATE;

      this.worklet.port.onmessage = (ev) => {
        const float32 = ev.data as Float32Array;
        if (!float32 || float32.length === 0) return;

        // Resample down à 16 kHz (linéaire simple)
        const outLen = Math.floor(float32.length / ratio);
        const resampled = new Float32Array(outLen);
        for (let i = 0; i < outLen; i++) {
          resampled[i] = float32[Math.floor(i * ratio)];
        }

        // RMS pour VAD
        let sumSq = 0;
        for (let i = 0; i < resampled.length; i++) sumSq += resampled[i] * resampled[i];
        const rms = Math.sqrt(sumSq / resampled.length);
        this.events.onLevel?.(rms);

        // Float32 → Int16
        const pcm = new Int16Array(resampled.length);
        for (let i = 0; i < resampled.length; i++) {
          const v = Math.max(-1, Math.min(1, resampled[i]));
          pcm[i] = v < 0 ? v * 0x8000 : v * 0x7fff;
        }
        this.pcmBuffer.push(pcm);

        const now = performance.now();
        if (rms > SILENCE_THRESHOLD) {
          if (this.speechStartedAt === null) this.speechStartedAt = now;
          this.lastVoiceAt = now;
        }

        // Flush si on a parlé puis silence prolongé
        if (
          this.speechStartedAt !== null &&
          now - this.lastVoiceAt > SILENCE_DURATION_MS &&
          this.lastVoiceAt - this.speechStartedAt > MIN_SPEECH_MS
        ) {
          this.flush();
        }
      };
    } catch (e) {
      this.events.onError?.(e as Error);
      throw e;
    }
  }

  private flush() {
    const total = this.pcmBuffer.reduce((s, c) => s + c.length, 0);
    if (total === 0) return;
    const merged = new Int16Array(total);
    let offset = 0;
    for (const chunk of this.pcmBuffer) {
      merged.set(chunk, offset);
      offset += chunk.length;
    }
    this.pcmBuffer = [];
    this.speechStartedAt = null;
    this.events.onChunk(merged.buffer);
    this.events.onFlush();
  }

  stop() {
    this.worklet?.disconnect();
    this.source?.disconnect();
    this.stream?.getTracks().forEach((t) => t.stop());
    this.ctx?.close();
    this.worklet = null;
    this.source = null;
    this.stream = null;
    this.ctx = null;
  }
}
