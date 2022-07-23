
from cost import SacSelfCost, TapCost
from game import Card, Player
from characteristics import Characteristics
from abilities import SimpleManaAbility, ActivatedAbility, SpellAbility
from effects import *


def build_deck(pl: Player, deck: list[Characteristics]):
    """Creates the given deck of cards, from their characteristics, in pl's library"""
    for c in deck:
        Card(zone=pl.library, chars=c, owner=pl)


basic_land_types = {"W": "plains", "U": "island",
                    "B": "swamp", "R": "mountain", "G": "forest"}
basic_land_cols = {c: t for t, c in basic_land_types.items()}


def basic_land(ty, snow=False):
    """Returns the charactaristics for a basic land of the given type/colour"""
    supertypes = "snow basic" if snow else "basic"
    prefix = "Snow-Covered " if snow else ""
    if ty in ["C", "wastes"]:
        # wastes isn't a subtype
        return Characteristics(
            name=prefix+"Wastes",
            supertypes=supertypes,
            types="land",
            abilities=[SimpleManaAbility("C")]
        )
    if ty in basic_land_types:
        col, ty = ty, basic_land_types[ty]
    else:
        col = basic_land_cols[ty]
    return Characteristics(
        name=prefix+ty.title(),
        supertypes=supertypes,
        types="land",
        subtypes=ty,
        abilities=[SimpleManaAbility(col)])


plains = basic_land("W")
island = basic_land("U")
swamp = basic_land("B")
mountain = basic_land("R")
forest = basic_land("G")
wastes = basic_land("C")

memnite = Characteristics(
    name="Memnite",
    cost=0,
    types="artifact creature",
    subtypes="construct",
    power=1,
    toughness=1
)

grizzly_bears = Characteristics(
    name="Grizzly Bears",
    cost="1G",
    types="creature",
    subtypes="bear",
    power=2,
    toughness=2
)

black_lotus = Characteristics(
    name="Black Lotus",
    cost=0,
    types="artifact",
    abilities=[SimpleManaAbility(
        col=c, amt=3, cost=TapCost()+SacSelfCost()) for c in "WUBRG"]
)


class GrowAbility(ActivatedAbility):
    def effect(self, you: Player, choices=None):
        put_counters(self.src, "+1/+1", 1)

    def __repr__(self):
        return f"({self.cost}: Put a +1/+1 counter on this)"


chronomaton = Characteristics(
    name="Chronomaton",
    cost=1,
    types="artifact creature",
    subtypes="consturct",
    power=1,
    toughness=1,
    abilities=[GrowAbility(1+TapCost())]
)


class LightningBoltEffect(SpellAbility):
    def make_choices(self, you: Player):
        return self.choose_targets(you, objectsets.damagable)

    def effect(self, you: Player, choices=None):
        damage(self.src, choices['targets'][0, 0], 3)


class ZapEffect(SpellAbility):
    def make_choices(self, you: Player):
        return self.choose_targets(you, objectsets.damagable)

    def effect(self, you: Player, choices):
        damage(self.src, choices['targets'][0, 0], 1)
        draw_cards(you, 1)


class ReclaimEffect(SpellAbility):
    def make_choices(self, you: Player):
        return self.choose_targets(you, objectsets.zone(you.graveyard))

    def effect(self, you: Player, choices=None):
        t = choices['targets'][0, 0]
        move(t, t.owner.library)


lightning_bolt = Characteristics(
    name="Lightning Bolt",
    cost="R",
    types="instant",
    abilities=[LightningBoltEffect()]
)

zap = Characteristics(
    name="Zap",
    cost="2R",
    types="instant",
    abilities=[ZapEffect()]
)

reclaim = Characteristics(
    name="Reclaim",
    cost="G",
    types="instant",
    abilities=[ReclaimEffect()]
)


class TimAbility(ActivatedAbility):
    def __init__(self):
        super().__init__(TapCost())

    def make_choices(self, you: Player):
        return self.choose_targets(you, objectsets.damagable)

    def effect(self, you: Player, choices):
        damage(self.src, choices['targets'][0, 0], 1)


tim = Characteristics(
    name="Prodigal Sorcerer",
    cost="2U",
    types="creature",
    subtypes="human wizard",
    power=1,
    toughness=1,
    abilities=[TimAbility()]
)
