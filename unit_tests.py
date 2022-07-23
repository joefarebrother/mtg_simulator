import game
from objectsets import ObjectSet
from players import *
from cards import *
from actions import start_game, do_turn


def card_named(name, zone):
    return [c for c in zone if c.name == name][0]


class TestPlayer(Player):
    def __init__(self, name: str, actions, verbose):
        super().__init__(name)
        self.actions = iter(actions)
        self.wait = None
        self.verbose = verbose

    def decide_action(self):
        if self.verbose:
            print_board()
        if self.wait:
            t, st = self.wait
            if not (t == game.turn_idx and st == game.turn.step.name):
                return None
            self.wait = None
        try:
            actd = next(self.actions)
        except StopIteration:
            return None
        if actd is None:
            return None
        if type(actd) == tuple:
            self.wait = actd
            return None

        _actd = actd
        kind = actd[0]
        actd = actd[1:].strip()
        ab = 0
        if '>' in actd:
            actd, target = actd.split(">")
            self.target = target.split(";")
        if '.' in actd:
            actd, ab = actd.split('.')
            ab = int(ab.strip())
        actd = actd.strip()
        if kind == "p":
            act = PlayCard(card_named(actd, self.hand))
        elif kind == "a":
            act = ActivateAbility(card_named(
                actd, game.battlefield).abilities[ab])
        if self.verbose:
            print(actd, act)
        assert act.can_take_action(self, None), _actd
        return act

    def decide_objects(self, obs: ObjectSet, reason=None, min: int = 1, max: int = None, order_matters=False):
        ts, self.target = self.target, None
        return [card_named(t, obs) for t in ts]


def test1_cast(verbose=False):
    game.clear_state()

    p0 = TestPlayer("Test1", [None, "p Forest", (2, "main"),
                              "p Mountain", "a Forest", "a Mountain", "p Grizzly Bears"], verbose)
    p1 = Goldfish("Goldfish1")

    deck = [memnite, mountain, forest, grizzly_bears]

    build_deck(p0, deck)

    start_game()

    for _ in range(5):
        do_turn()

    if verbose:
        print_board()


test1_cast()


def test2_act_ab(verbose=False):
    game.clear_state()

    p0 = TestPlayer("Test2", [None, "p Wastes", "a Wastes", "p Chronomaton",
                              (3, "end"), "a Wastes", "a Chronomaton",
                              (5, "end"), "a Wastes", "a Chronomaton"], verbose)
    p1 = Goldfish("Goldfish2")

    deck = [wastes, chronomaton]

    build_deck(p0, deck)

    start_game()

    for _ in range(6):
        do_turn()

    c = card_named("Chronomaton", game.battlefield)

    assert (c.power, c.toughness) == (3, 3)

    if verbose:
        print_board()


test2_act_ab()


def test3_targets_fizzle(verbose=False):
    game.clear_state()

    p0 = TestPlayer("Test3", [None, "p Memnite", None, "p Mountain", "p Black Lotus",
                              None, "a Mountain", "a Black Lotus.3", "p Zap>Memnite", "p Lightning Bolt>Memnite"], verbose)
    p1 = Goldfish("Goldfish3")

    deck = [wastes]*10 + [memnite, mountain, black_lotus, lightning_bolt, zap]

    build_deck(p0, deck)

    start_game()

    for _ in range(1):
        do_turn()

    assert len(p0.library) == len(deck)-7

    if verbose:
        print_board()


test3_targets_fizzle()
