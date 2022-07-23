import game
import mana
import effects
from game import Player, GameObject


class PaymentFailed(Exception):
    pass


class Cost:
    """A cost that can be payed"""

    def colours(self) -> set:
        """Returns the set of colours an object with this cost has"""
        return set()

    def mana_value(self) -> int:
        """Returns the mana value that an object with this cost has"""
        return 0

    def can_pay(self, player: Player, obj=None, choices=None) -> bool:
        """Returns true if it is possible to pay this cost"""
        pass

    def pay(self, player: Player, obj=None, choices=None):
        """Pays the cost"""
        pass

    def __add__(self, other):
        if isinstance(other, NullCost):
            return other
        if isinstance(other, FreeCost):
            return self
        if isinstance(other, Cost):
            return CompoundCost(self, other)
        if isinstance(other, int):
            if other == 0:
                return self
            if other > 0:
                return self + ManaCost(other)
        if isinstance(other, str) or isinstance(other, dict):
            return self + ManaCost(other)
        return NotImplemented

    __radd__ = __add__

    def __repr__(self):
        return str(self)


class NullCost(Cost):
    """The empty cost, which is unpayable"""

    def can_pay(self, player, obj=None, choices=None) -> bool:
        return False

    def __add__(self, other):
        if isinstance(other, Cost):
            return self
        return NotImplemented

    def __str__(self):
        return "<null>"


class FreeCost(Cost):
    """The free cost, which is always payable"""

    def can_pay(self, player, obj=None, choices=None) -> bool:
        return True

    def pay(self, player, obj=None, choices=None):
        pass

    def __add__(self, other):
        if isinstance(other, Cost):
            return other
        return NotImplemented

    def __str__(self):
        return "0"


class ManaCost(Cost):
    """A mana cost"""

    def __init__(self, c):
        self.mana = mana.mana(c, True)

    def colours(self) -> set:
        return set(c for c in "WUBRG" if self.mana[c] > 0)

    def mana_value(self) -> int:
        return sum(self.mana.values())

    def can_pay(self, player, obj=None, choices=None) -> bool:
        pool = player.mana_pool.payable_for(obj)
        total = sum(pool.values())
        for c, x in self.mana.items():
            if c == "gen":
                continue
            if pool[c] < x:
                return False
            total -= x
        return total >= self.mana["gen"]

    def pay(self, player, obj=None, choices=None):
        # todo: choices for specific mana
        # innacuracy: should be able to activate mana abilities
        for c, x in self.mana.items():
            left = player.mana_pool.spend(c, x, obj, choices)
            if left:
                raise PaymentFailed()

    def __add__(self, other):
        if isinstance(other, ManaCost):
            res = self.mana.copy()
            for ty in res:
                res[ty] += other[ty]
            return ManaCost(res)
        return super().__add__(other)

    def __str__(self):
        return mana.mana_str(self.mana)


class CompoundCost(Cost):
    """A combination of two or more other costs"""

    def __init__(self, *costs):
        costs2 = []
        for c in costs:
            if isinstance(c, CompoundCost):
                costs2 += c.costs
            else:
                costs2.append(c)
        mana_costs = []
        other_costs = []
        for c in costs2:
            if isinstance(c, ManaCost):
                mana_costs.append(c)
            else:
                other_costs.append(c)
        if mana_costs:
            mana_costs = iter(mana_costs)
            total = next(mana_costs)
            for m in mana_costs:
                total += m
            other_costs = [total]+other_costs
        self.costs = other_costs

    def can_pay(self, player, obj=None, choices=None) -> bool:
        # may not be fully accurate in case for costs that include the same resource; e.g. sac a creature
        return all(c.can_pay(player, obj, choices) for c in self.costs)

    def pay(self, player: Player, obj=None, choices=None):
        for c in self.costs:
            c.pay(player, obj, choices)

    def __str__(self):
        return ", ".join(str(c) for c in self.costs)


class TapCost(Cost):
    """The tap symbol cost"""

    def can_pay(self, player, ab, choices=None) -> bool:
        src = ab.src
        if not(src and src.controller == player and src.zone == game.battlefield):
            return False
        return src.can_tap()

    def pay(self, player, ab, choices=None):
        effects.tap(ab.src)

    def __str__(self):
        return "T"


class SacSelfCost(Cost):
    def can_pay(self, player: Player, ab, choices=None) -> bool:
        src = ab.src
        if src.controller != player or src.zone != game.battlefield or src.dead:
            return False
        return True

    def pay(self, player: Player, ab, choices=None):
        src = ab.src
        src.move_to(src.owner.graveyard)

    def __str__(self):
        return "Sac this"
