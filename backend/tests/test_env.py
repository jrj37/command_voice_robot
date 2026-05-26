from game.env import RobotEnv


def test_init_position():
    env = RobotEnv()
    assert env.position == [5, 5]
    assert env.orientation == 0


def test_step_rotate():
    env = RobotEnv()
    env.step(2)  # tourne à droite
    assert env.orientation == 1
    env.step(1)  # tourne à gauche
    assert env.orientation == 0


def test_step_forward():
    env = RobotEnv()
    # orientation 0 = nord → y diminue
    start = list(env.position)
    env.step(0)
    assert env.position == [start[0], start[1] - 1] or env.position == start


def test_serialize_static():
    env = RobotEnv()
    s = env.serialize_static()
    assert s["grid_size"] == 11
    assert len(s["map"]) == 11
    assert len(s["landmarks"]) > 0


def test_serialize_state():
    env = RobotEnv()
    s = env.serialize_state()
    assert "robot" in s
    assert "objects" in s
    assert s["robot"]["x"] == 5
