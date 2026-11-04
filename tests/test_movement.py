"""Movement modes: walking, stamina-gated sprinting and quiet sneaking."""

import math

import server


def player(**over):
    p = {
        "mx": 1.0, "my": 0.0, "stamina": 80.0,
        "running": False, "sneaking": False,
        "stats": {"agility": 1},
    }
    p.update(over)
    return p


def test_walk_speed_is_the_baseline():
    speed, running, sneaking = server.player_move_profile(player())
    assert speed == server.WALK_SPEED_BASE
    assert not running and not sneaking


def test_running_is_faster_than_walking():
    walk, _, _ = server.player_move_profile(player())
    run, running, sneaking = server.player_move_profile(player(running=True))
    assert running and not sneaking
    assert run == walk * server.RUN_SPEED_FACTOR
    assert run > walk


def test_sneaking_is_slow():
    walk, _, _ = server.player_move_profile(player())
    sneak, running, sneaking = server.player_move_profile(player(sneaking=True))
    assert sneaking and not running
    assert sneak == walk * server.SNEAK_SPEED_FACTOR
    assert sneak < walk


def test_sprint_needs_stamina():
    exhausted = server.player_move_profile(player(running=True, stamina=0.4))
    assert exhausted[1] is False
    assert exhausted[0] == server.WALK_SPEED_BASE

    rested = server.player_move_profile(player(running=True, stamina=40.0))
    assert rested[1] is True


def test_movement_modes_need_a_direction():
    idle = server.player_move_profile(player(mx=0.0, my=0.0, running=True, sneaking=True))
    assert idle[1] is False and idle[2] is False
    assert idle[0] == server.WALK_SPEED_BASE


def test_sneaking_wins_over_running():
    speed, running, sneaking = server.player_move_profile(player(running=True, sneaking=True, stamina=90))
    assert sneaking and not running
    assert speed == server.WALK_SPEED_BASE * server.SNEAK_SPEED_FACTOR


def test_agility_scales_speed():
    slow, _, _ = server.player_move_profile(player(stats={"agility": 1}))
    fast, _, _ = server.player_move_profile(player(stats={"agility": 11}))
    assert math.isclose(fast - slow, 10 * 3.2)
