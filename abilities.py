from __future__ import annotations
from collections import defaultdict
from typing import TYPE_CHECKING
from characteristics import Characteristics
from objectsets import ObjectSet

if TYPE_CHECKING:
    from game import Player, Zone

from util import *
from cost import Cost, TapCost
import game


class Ability:
    src = None
    """
An ability; as defined by 113.1a and 113.1b as a charactaristic that an object or player can have that effects the game.
The other usage of 'ability' in the rules (113.1c) (an object on the stack) is represented by AbilityOnTheStack. 
    """

    def active_zones(self):
        """Returns the set of zones for which this ability is active"""
        return {game.battlefield}

    def __copy__(self):
        a = copy_excluding(self, ["src"])
        a.src = None
        return a

    def bind(self, src):
        """Binds this ability to its source. Two game objects must not have the same ability object; they must use a copy"""
        assert self.src is None
        self.src = src

    def __repr__(self):
        if self.src:
            return f"{type(self).__name__} of {self.src}"
        else:
            return type(self).__name__


class Targets:
    def __init__(self) -> None:
        self.targets = {}

    def next_idx(self) -> int:
        mx = 0
        for i in self.targets:
            if type(i) == int:
                mx = max(mx, i+1)
        return mx

    # todo: sometimes the controller of the ability is not the same one making the choice
    def choose(self, ab: EffectThatCanGoOnTheStack, you: Player, options: ObjectSet, min=1, max=None, idx=None, order_matters=False):
        if idx == None:
            idx = self.next_idx()
        assert idx not in self.targets
        if max is None:
            max = min

        ch = options.filter(lambda x: can_target(ab, you, x)).choose(
            you, ('target', ab), min, max, order_matters)

        self.targets[idx] = (ch, options, ab, order_matters)

    # todo: some targets are chosen by players other than the controller
    # also rechoosing targets (deflecting swat, bolt bend)

    def __getitem__(self, idx):
        if type(idx) == tuple:
            idx, sub = idx
            ch = self.targets[idx][0]
            if sub < len(ch):
                return ch[sub]
            return None
        if type(idx) == int:
            return self.targets[idx][0]

    def should_fizzle(self, you: Player):
        if len(self.targets) == 0:
            return False
        any_legal = False
        for (ch, options, ab, _) in self.targets.values():
            for i, t in enumerate(ch):
                if t and t in options and can_target(ab, you, t):
                    any_legal = True
                else:
                    ch[i] = None
        return not any_legal


class EffectThatCanGoOnTheStack(Ability):
    """An effect that can go on the stack, such as an activated or triggered ability, or a spell ability
    TODO: think of a better name (2 hardest things in CS)"""

    def make_choices(self, you: Player):
        """Makes the choices for a spell or ability, such as value for X, modes, and targets"""
        return None

    def choose_targets(self, you: Player, options: ObjectSet, min=1, max=None, idx=None, order_matters=False, choices=None):
        if choices is None:
            choices = {}
        if 'targets' not in choices:
            choices['targets'] = Targets()
        choices['targets'].choose(
            self, you, options, min, max, idx, order_matters)
        return choices

    def effect(self, you: Player, choices):
        return None

    def should_fizzle(self, you: Player, choices):
        if choices is None:
            return False
        if 'targets' not in choices:
            return False
        return choices['targets'].should_fizzle(you)


def can_target(ab: EffectThatCanGoOnTheStack, controller: Player, target: game.GameObject):
    """Returns true if target is a valid target for an ability ab (incl. a spell ability which comes from a spell) controlled by the given player
    ab.src is the src of the ability (either a spell or the object with the ability), which may not necassarily have the same controller.
    """
    if not target:
        return False
    # 115.5. A spell or ability on the stack is an illegal target for itself.
    # agh; this actually requires passing around the original stack object...
    if target.zone == game.stack and (target == ab.src or (isinstance(target, _SpellAbWrapper) and target.ab_src == ab)):
        return False
    # todo: check for protection, hexproof, etc; with general permission system
    return True


class SpellAbility(EffectThatCanGoOnTheStack):
    pass

# passing the ab EffectThatCanGoOnTheStack + controller seems to preserve all the info needed
# the original src is ab.src, whose controller is not necassarily the same; and whether ab is a spell or an ability
# is determined by whether it is an instance of SpellAbility.
# ugh; except for the 'can't target yourself' rule... where just checking the target has the same ab_src is innacurate
# due to stopping different instances of the ability for targetting each other

# todo: rework spells and abilities to actually go on the stack while casting them
# so this can be properly implemented


class _SpellAbWrapper(SpellAbility):
    def __init__(self, ab_src: EffectThatCanGoOnTheStack):
        self.ab_src = ab_src

    def make_choices(self, you: Player):
        return self.ab_src.make_choices(you)

    def effect(self, you: Player, choices):
        self.ab_src.effect(you, choices)


class AbilityOnTheStack(game.CardLike):
    """An activated or triggered ability on the stack."""

    def __init__(self, ab_src, choices, **kwargs):
        self.ab_src = ab_src
        self.src = ab_src.src
        super().__init__(chars=Characteristics(
            name=self.src.name + " ability",
            types="ability",
            abilities=[_SpellAbWrapper(ab_src)]), zone=game.stack, **kwargs)
        self.spell_choices = choices

    def move_to(self, newzone: Zone):
        self.delete()
        return self


class KeywordAbility(Ability):
    """A keyword ability"""

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return self.name


class ActivatedAbility(EffectThatCanGoOnTheStack):
    """An activated ability"""
    mana_ability: bool = False
    sorcery_only: bool = False

    def __init__(self, cost: Cost):
        self.cost = cost
        self.src = None

    def can_activate(self, you: Player, choices):
        """Returns true if it is possible for this you to activate this ability"""
        from actions import can_cast_sorcery
        if self.src.dead:
            return False
        if self.sorcery_only and not can_cast_sorcery(you):
            return False
        if self.src.zone not in self.active_zones():
            return False
        if not you == self.src.controller:
            return False
        if not self.cost.can_pay(you, self, choices):
            return False
        return True

    def activate(self, you: Player, choices):
        """Activates the ability"""
        self.cost.pay(you, self, choices)
        if self.mana_ability:
            self.effect(you, choices)
        else:
            AbilityOnTheStack(self, choices, owner=you)
            pass


class TriggeredAbility(EffectThatCanGoOnTheStack):
    """A triggered ability"""
    # todo
    pass


class StaticAbility(Ability):
    """A static ability"""
    pass


class SimpleManaAbility(ActivatedAbility):
    """The ability that taps to add mana of a certain colour and amount, doing nothing else special"""
    mana_ability: bool = True

    def __init__(self, col, amt: int = 1, cost: Cost = TapCost(), sorcery=False):
        super().__init__(cost=cost)
        self.sorcery_only = sorcery
        self.col = col
        self.amt = amt

    def effect(self, you: Player, choices=None):
        you.mana_pool[self.col] += self.amt

    def __repr__(self):
        return f"({self.cost}: Add {self.col*self.amt})"
