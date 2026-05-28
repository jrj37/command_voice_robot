import ReactDOM from "react-dom/client";
import { App } from "./App";
import "./styles.css";

// Pas de StrictMode : Pixi.js (v8) ne supporte pas le double-mount des effets
// en dev — la 2e initialisation de l'Application sur le même canvas casse le
// contexte WebGL partagé.
ReactDOM.createRoot(document.getElementById("root")!).render(<App />);
