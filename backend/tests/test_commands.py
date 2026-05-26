from voice.commands import parse


def test_action_avance():
    assert parse("avance").kind == "action"
    assert parse("avance").action == 0


def test_action_gauche():
    p = parse("tourne à gauche")
    assert p.kind == "action"
    assert p.action == 1


def test_stop():
    assert parse("stop").kind == "stop"
    assert parse("quitter").kind == "stop"


def test_agent_simple():
    p = parse("récupère les clés")
    assert p.kind == "agent"
    assert p.target_type == "clé"


def test_agent_count_word():
    p = parse("cherche trois gemmes")
    assert p.kind == "agent"
    assert p.target_type == "gemme"
    assert p.count == 3


def test_hint():
    p = parse("près de la fontaine")
    assert p.kind == "hint"
    assert p.landmark == "fontaine"


def test_unknown():
    assert parse("blah blah").kind == "unknown"


def test_fuzzy():
    # léger typo
    assert parse("avancr").kind == "action"
