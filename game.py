from __future__ import annotations
from typing import TYPE_CHECKING
from typing import Optional


if TYPE_CHECKING:
    from characteristics import Characteristics
    from actions import Action
    from objectsets import ObjectSet
    from turn import Turn

from collections import OrderedDict
from copy import copy
from dataclasses import dataclass
from typing import Counter


next_id = 0


def fresh_id():
    global next_id
    next_id += 1
    return next_id


class Zone:
    """A zone that can contain objects. A zone is ordered."""

    def __init__(self, name: str):
        self.name = name
        self.objects = OrderedDict()

    def __iter__(self):
        yield from self.objects.values()

    def __len__(self):
        return len(self.objects)

    def get_top(self):
        """Gets the object most recently added to this zone"""
        return next(reversed(self.objects.values()))

    def __str__(self):
        return self.name


objects = {}
battlefield = Zone("battlefield")
exile = Zone("exile")
stack = Zone("stack")
players = []
turn_idx = 0
turn: Turn = None
next_turns = []
winner = None


def clear_state():
    global turn_idx, turn, next_turns, winner
    for o in list(objects.values()):
        if isinstance(o, CardLike):
            o.delete()
    players.clear()
    turn_idx = 0
    turn = None
    next_turns = []
    winner = None


class GameOver(Exception):
    """Raised when the game ends."""
    pass


class GameObject:
    """An object, as defined by 109.1; except that players are also included for convinience."""

    def __init__(self, zone: Zone, chars: Characteristics, owner: Player = None, controller: Player = None):
        from characteristics import CounterChars
        self.id = fresh_id()
        self.dead = False
        self.new = None
        self.zone = zone
        objects[self.id] = self
        if zone is not None:
            zone.objects[self.id] = self
        self.owner = owner
        self.base_controller = controller or owner
        self.base_chars = copy(chars)
        self.chars = CounterChars(self)
        self.base_chars.bind(self)
        self.permstate = None if zone != battlefield else PermanentState()
        self.spell_choices = None
        self.counters = Counter()

    @property
    def controller(self) -> Player:
        return self.base_controller

    def direct_move(self, newzone: Zone) -> GameObject:
        """
        Moves this object to the specified zone directly. Replacement effects and triggered abilities aren't applied.
        This creates and returns a new object.
        """
        if self.dead:
            return None

        oldzone = self.zone
        new_controller = self.controller

        if newzone not in [battlefield, stack]:
            new_controller = self.owner

        new = type(self)(zone=newzone, chars=self.base_chars,
                         owner=self.owner, controller=new_controller)

        del objects[self.id]
        del oldzone.objects[self.id]
        self.dead = True
        self.new = new

        return new

    def move_to(self, newzone: Zone) -> GameObject:
        """
        Moves this object to the specified zone. 
        """
        from effects import move
        move(self, newzone)
        return self.new

    def delete(self):
        """
        Deletes this object, removing it from the game entirely.
        """
        if self.zone:
            del self.zone.objects[self.id]
        del objects[self.id]
        self.zone = None
        self.dead = True
        self.new = None

    def __repr__(self):
        return f"{self.name} {self.id}" + (" (T)" if self.permstate and self.permstate.tapped else "")

    def __getattr__(self, attr):
        if hasattr(self.base_chars, attr) and attr not in ["src", "bind"] and not attr.startswith("_"):
            return getattr(self.chars, attr)
        raise AttributeError(attr)

    def __bool__(self):
        return not self.dead


class Player(GameObject):
    """A player."""

    def __init__(self, name: str):
        from mana import ManaPool
        from characteristics import Characteristics
        super().__init__(zone=None, chars=Characteristics(
            name=name), owner=self, controller=self)
        self.life = 20
        self.hand = Zone(name + " hand")
        self.graveyard = Zone(name + " graveyard")
        self.library = Zone(name + " library")
        players.append(self)
        self.mana_pool = ManaPool()
        self.lands_played = 0

    def move_to(self, newzone: Zone):
        assert False

    def draw(self, n: int = 1):
        """Draws n cards. Replacement effects are not yet implemented."""
        for _ in range(n):
            if self.library:
                self.library.get_top().move_to(self.hand)

    def decide_action(self) -> Optional[Action]:
        """Decides an action when this player has priority. Override to implement various behaviours."""
        return None

    def decide_objects(self, obs: ObjectSet, reason=None, min: int = 1, max: int = None, order_matters=False):
        """Decides a choice of objects, such as targets"""
        return None

    def decide_attacks(self):
        """Decides what creatures to attack with.
        Return a list to attack at the next player, or a dict to choose which players and pws are attacked.
        """
        return None

    def decide_blocks(self, atks: dict) -> list:
        """Given a dict of creatures attacking you and pws you control, choose which creatures to block with."""
        return None

    def decide_order(self, objects: list, reason=None) -> list:
        """Given a list of objects, choose what order they should be in"""
        return None

    def decide_damage(self, orders: dict):
        """Decides how to assign combat damage"""
        return None

    def __str__(self):
        return self.name

    def use_tournament_locator(self):
        """
        100.6b Players can use the Magic Store & Event Locator at Wizards.com/Locator to find tournaments in their area
        """
        import os
        os.system("firefox wizards.com/locator")


@dataclass
class PermanentState:
    """The additional state that a permanent can have."""
    tapped: bool = False
    summoning_sick: bool = True
    used_loyalty: bool = False
    damage: int = 0
    deathtouch_damage: bool = False
    attacked_obj: GameObject = None
    defending_player: Player = None


class CardLike(GameObject):
    """An object that is not a player; as defined by 109.1"""

    def resolve(self):
        """Resolves this object from the stack."""
        import abilities
        assert self.zone == stack
        if self.is_permanent_type():
            self.move_to(battlefield)
            return
        for a in self.abilities:
            if isinstance(a, abilities.SpellAbility):
                if not a.should_fizzle(self.controller, self.spell_choices):
                    a.effect(self.controller, self.spell_choices)
                break
        self.move_to(self.owner.graveyard)

    def can_tap(self) -> bool:
        """Returns true if this object can attack or acticate a tap ability"""
        if not (self and self.zone == battlefield):
            return False
        if self.permstate.tapped:
            return False
        return not self.permstate.summoning_sick or self.has_keyword("haste") or not self.has_type("creature")


class Card(CardLike):
    pass


class Token(CardLike):
    pass


def next_player(p: Player) -> Player:
    """Returns the player next in turn order after p"""
    ps = iter(players + [players[0]])
    for q in ps:
        if p == q:
            return next(ps)
    assert False
