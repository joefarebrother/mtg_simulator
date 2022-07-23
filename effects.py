import game
import objectsets
import abilities
from game import GameObject, GameOver, Player, CardLike, Zone


class _Simultaneously:
    def __enter__(self):
        pass

    def __exit__(self, *args):
        pass


simultaneously = _Simultaneously()


def event(*args):
    pass


def win_game(pl: Player):
    game.winner = pl
    raise GameOver()


def lose_game(pl: Player):
    # todo: multiplayer removing the player's stufff
    pl.delete()
    game.players = [p for p in game.players if p != pl]
    if len(game.players) == 1:
        game.winner = game.players[0]
        raise GameOver()


def move(ob: CardLike, newzone: Zone):
    oldzone = ob.zone
    if ob.dead:
        return
    if oldzone == newzone and oldzone != game.exile:
        return
    event("move_pre", ob, oldzone, newzone)
    new = ob.direct_move(newzone)
    event("move_post", ob, oldzone, newzone)


def destroy(ob: CardLike, no_regen=False):
    if ob.zone != game.battlefield:
        return
    move(ob, ob.owner.graveyard)


def lose_life(pl: Player, amt: int):
    amt = max(amt, 0)
    if amt == 0:
        return
    pl.life -= amt


def gain_life(pl: Player, amt: int):
    amt = max(amt, 0)
    if amt == 0:
        return
    pl.life -= amt


def set_life(pl: Player, amt: int):
    if amt >= pl.life:
        gain_life(pl, amt-pl.life)
    else:
        lose_life(pl, pl.life-amt)


def put_counters(ob: GameObject, kind: str, amt: int):
    ob.counters[kind] += amt


def remove_counters(ob: GameObject, kind: str, amt: int):
    ob.counters[kind] = max(ob.counters[kind] - amt, 0)


def damage(src: CardLike, target: GameObject, amt: int, combat=False):
    assert not isinstance(src, abilities.AbilityOnTheStack)
    if amt <= 0:
        return
    if not target in objectsets.damagable:
        return
    if isinstance(target, Player):
        if src.has_keyword("infect"):
            put_counters(target, "poison", amt)
        else:
            lose_life(target, amt)
    else:
        if target.has_type("creature"):
            if src.has_keyword("infect") or src.has_keyword("wither"):
                put_counters(target, "-1/-1", amt)
            else:
                target.permstate.damage += amt
            if src.has_keyword("deathtouch"):
                target.permstate.deathtouch_damage = True
        if target.has_type("planeswalker"):
            remove_counters(target, "loyalty", amt)
    if src.has_keyword("lifelink"):
        gain_life(src.controller, amt)


def draw_cards(pl: Player, amt: int = 1):
    pl.draw(amt)


def tap(ob):
    if not(ob and ob.zone == game.battlefield):
        return
    ob.permstate.tapped = True


def untap(ob):
    if not(ob and ob.zone == game.battlefield):
        return
    ob.permstate.tapped = False
