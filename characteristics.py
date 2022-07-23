from copy import copy
from util import *
from dataclasses import dataclass, field
from cost import Cost, NullCost, ManaCost
import re
import game
import abilities


@dataclass
class Characteristics:
    """The charactaristics of an object"""
    name: str = None
    cost: Cost = NullCost()
    supertypes: list = field(default_factory=list)
    types: list = field(default_factory=list)
    subtypes: list = field(default_factory=list)
    colours: set = None
    power: int = 0
    toughness: int = 0
    starting_loyalty: int = 0
    abilities: list = field(default_factory=list)

    def __post_init__(self):
        if not isinstance(self.cost, Cost):
            self.cost = ManaCost(self.cost)
        if self.colours is None:
            if self.cost is None:
                self.colours = set()
            else:
                self.colours = self.cost.colours()
        self.mana_value = self.cost.mana_value()

        if type(self.supertypes) == str:
            self.supertypes = self.supertypes.split()
        if type(self.types) == str:
            self.types = self.types.split()
        if type(self.subtypes) == str:
            self.subtypes = self.subtypes.split()
        self.supertypes = [st.lower() for st in self.supertypes]
        self.types = [st.lower() for st in self.types]
        self.subtypes = [st.lower() for st in self.subtypes]

        if self.name is None:
            self.name = " ".join(t.title() for t in self.subtypes) + " Token"

        self.src = None

    def has_type(self, ty: str):
        """Returns true if this object has the given type"""
        return ty.lower() in self.types

    def has_subtype(self, ty: str):
        """Returns true if this object has the given subtype"""
        return ty.lower() in self.subtypes

    def has_keyword(self, key: str):
        """Returns true if this oject has a keyword abilitiy of the given name"""
        if isinstance(key, abilities.KeywordAbility):
            key = key.name
        key = key.lower()
        return any(isinstance(ab, abilities.KeywordAbility) and ab.name == key for ab in self.abilities)

    def is_permanent_type(self):
        """Returns true if this object is a permanent"""
        return not (self.has_type("instant") or self.has_type("sorcery") or self.has_type("ability"))

    def __copy__(self):
        c = {k: getattr(self, k) for k in Characteristics.__dataclass_fields__}
        c = Characteristics(**c)
        c.abilities = [copy(a) for a in c.abilities]
        return c

    def bind(self, src):
        """Binds this set of characteristics to an object. Two objects may not share the same characteristics; they must use a copy."""
        assert self.src is None
        self.src = src
        for a in self.abilities:
            a.bind(src)


class CounterChars:
    """Temporary implementation of counters before layers are implemented"""

    def __init__(self, src):
        self.src = src

    def __getattr__(self, attr):
        if attr not in ["power", "toughness"]:
            return getattr(self.src.base_chars, attr)
        base = self.src.base_chars
        pow, tou = base.power, base.toughness
        for kind, amt in self.src.counters.items():
            m = re.fullmatch(r'([+-]\d+)/([+-]\d+)', kind)
            if m:
                pow += int(m.groups()[0]) * amt
                tou += int(m.groups()[1]) * amt
        return {"power": pow, "toughness": tou}[attr]

    __repr__ = Characteristics.__repr__
