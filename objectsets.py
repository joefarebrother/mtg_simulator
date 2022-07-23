from math import perm
import game
from game import GameObject, Player, Zone
from itertools import chain


class NoChoices(Exception):
    pass


class ObjectSet:
    """A set of game objects. Not fixed; rather checks the current gamestate when queried."""

    def contains(self, x: GameObject):
        """Returns true if this set contains this object"""
        return False

    def iter(self):
        """Enumerates the objects in this set. Should be equivilant to (x for x in game.objects if self.contains(x))"""
        return []

    def choose(self, pl: Player, reason=None, min=1, max=None, order_matters=False):
        """Chooses some number of these objects. If there are no possible choices, raises NoChoices. 
        If there is only one possible choice, returns it directly"""
        if max is None:
            max = min
        assert max >= min
        l = len(self)
        if min > l:
            raise NoChoices
        if min == l:
            if min == 1 or not order_matters:
                return list(self)[:min]
        ch = pl.decide_objects(self, reason, min, max, order_matters)
        if ch is None:
            return list(self)[:min]
        ch = list(ch)
        assert min <= len(ch) == len(set(ch)) <= max
        assert all(x in self for x in ch)
        return ch

    def __contains__(self, x):
        return self.contains(x)

    def __iter__(self):
        return iter(self.iter())

    def __len__(self):
        return sum(1 for _ in self)

    def __and__(self, other):
        return self.filter(lambda x: x in other)

    def __or__(self, other):
        return _FObset(lambda x: x in self or x in other, lambda: set(self) | set(other))

    def filter(self, cond):
        return _FObset(lambda x: self.contains(x) and cond(x), lambda: (x for x in self if cond(x)))

    def controlled_by(self, pl: Player):
        return self.filter(lambda x: x.controller == pl)

    def not_controlled_by(self, pl: Player):
        return self.filter(lambda x: x.controller != pl)

    def with_type(self, ty: str):
        return self.filter(lambda x: x.has_type(ty))

    def without_type(self, ty: str):
        return self.filter(lambda x: not x.has_type(ty))

    def with_subtype(self, ty: str):
        return self.filter(lambda x: x.has_subtype(ty))

    def without_subtype(self, ty: str):
        return self.filter(lambda x: not x.has_subtype(ty))

    def with_keyword(self, ty: str):
        return self.filter(lambda x: x.has_keyword(ty))

    def without_keyword(self, ty: str):
        return self.filter(lambda x: not x.has_keyword(ty))

    def other_than(self, obj: GameObject):
        return self.filter(lambda x: x != obj)

    def is_tapped(self):
        return self.filter(lambda x: x.permstate and x.permstate.tapped)

    def is_untapped(self):
        return self.filter(lambda x: x.permstate and not x.permstate.tapped)


class _FObset(ObjectSet):
    def __init__(self, contains, iter=None):
        self._contains = contains
        self._iter = iter or (lambda: (x for x in game.objects if contains(x)))

    def contains(self, x):
        return self._contains(x)

    def iter(self):
        return self._iter()


all_objects = _FObset(lambda x: not x.dead,
                      lambda: game.objects.values())


def zone(z: Zone):
    return _FObset(lambda x: x.zone == z and not x.dead, lambda: list(z))


permanents = zone(game.battlefield)
nonland_permanents = permanents.without_type("land")
creatures = permanents.with_type("creature")


class _Players(ObjectSet):
    def contains(self, x: GameObject):
        return isinstance(x, Player)

    def iter(self):
        return game.players


players = _Players()
damagable = players | permanents.with_type(
    "creature") | permanents.with_type("planeswalker")


def opponents_of(you: Player):
    return players.other_than(you)


class _GraveCards(ObjectSet):
    def contains(self, x: GameObject):
        return x.zone == x.owner.graveyard

    def iter(self):
        return chain(*(x.graveyard for x in players))


graveyard_cards = _GraveCards
