from dataclasses import dataclass

from numpy import isin
import game
from game import Player, Card
from objectsets import NoChoices
import turn as T
from abilities import ActivatedAbility, SpellAbility


class ActionFailed(Exception):
    pass


def can_cast_sorcery(p: Player):
    """Returns true if p could cast a sorcery; i.e. it's their main phase and the stack is empty."""
    return p == game.turn.active_player and isinstance(game.turn.phase, T.MainPhase) and len(game.stack) == 0


def can_play_land(p: Player):
    """Returns true if p could play a land; i.e. it's their turn and they haven't played a land yet this game.turn.
    TODO: implement extra land drop effects."""
    return p.lands_played < 1 and game.turn.active_player == p


class Action:
    """An action that a player can take when they have priority"""

    def make_choices(self, p: Player) -> dict:
        """Makes the necassary choices for an action, such as targets"""
        return False

    def can_take_action(self, p: Player, choices=None) -> bool:
        """Returns true if p can take this action"""
        return False

    def take_action(self, p: Player, choices=None):
        """Takes the action"""
        pass


@dataclass
class PlayCard(Action):
    card: Card

    def make_choices(self, p: Player) -> dict:
        for ab in self.card.abilities:
            if isinstance(ab, SpellAbility):
                return ab.make_choices(p)

    def can_take_action(self, p: Player, chocies=None):
        c = self.card
        if c.dead:
            return False

        if not c.zone == p.hand:
            return False  # todo: alt casting permissions

        if not can_cast_sorcery(p) and not (c.has_type("instant") or c.has_keyword("flash")):
            return False

        if c.has_type("land"):
            if not can_play_land(p):
                return False
        else:
            if not c.cost.can_pay(p):
                return False  # todo: alt/add costs, other choices that affect the cost like X

        return True

    def take_action(self, p: Player, choices=None):
        c = self.card
        if c.has_type("land"):
            c.move_to(game.battlefield)
            p.lands_played += 1
        else:
            # innacuracy: stuff should be moved to the stack before costs are paid and other choices are made
            c.cost.pay(p, c)
            nc = c.move_to(game.stack)
            nc.spell_choices = choices
        c.base_controller = p


@dataclass
class ActivateAbility(Action):
    ab: ActivatedAbility

    def make_choices(self, p: Player) -> dict:
        return self.ab.make_choices(p)

    def can_take_action(self, p: Player, choices):
        return self.ab.can_activate(p, choices)

    def take_action(self, p: Player, choices):
        self.ab.activate(p, choices)


def start_game(first: Player = None):
    """Starts the game"""
    if first is None:
        first = game.players[0]
    for p in game.players:
        p.draw(7)
    game.turn = T.Turn(first)
    game.turn.phase.skip_step("draw")


def do_turn():
    """Simulate one turn of the game"""
    t = game.turn
    t.start()
    while not t.finished:
        pri = t.priority
        act = pri.decide_action()
        if act is None:
            t.pass_priority()
        else:
            try:
                ch = act.make_choices(pri)
            except NoChoices:
                print("No possible choices")
                continue
            if act.can_take_action(pri, ch):
                act.take_action(pri, ch)
                t.take_action()
            else:
                print("Illegal action")
    game.turn_idx += 1
    nt = T.Turn(game.next_player(t.active_player))
    game.turn = nt
