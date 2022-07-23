from dataclasses import dataclass

mana_types = "CWUBRG"


def mana(x, generic=False):
    """Converts a description x of a mana cost or ammount into a dict for the amount of each colour. 
    If generic is true, numbers are interpreted as generic mana and are placed in the key 'gen' of the result."""
    if isinstance(x, dict):
        m = {c: (x[c] if c in x else 0) for c in mana_types}
        if generic:
            m["gen"] = x.get("gen", 0)
        return m
    if isinstance(x, int):
        m = mana({})
        if generic:
            m["gen"] = x
        else:
            m["C"] += x
        return m
    if isinstance(x, SpecialMana):
        return x
    if isinstance(x, str):
        m = mana({})
        if generic:
            m["gen"] = 0
        for c in x:
            if c in "0123456789":
                if generic:
                    m["gen"] += int(c)
                else:
                    m["C"] += int(c)
            else:
                m[c] += 1
        return m
    raise TypeError(x)


def mana_str(x: dict) -> str:
    """Returns a string representation of the given mana dict"""
    res = ""
    if "gen" in x:
        if x["gen"]:
            res += str(int(x["gen"]))
        tys = mana_types
    else:
        if x["C"]:
            res += str(int(x["C"]))
        tys = "WUBRG"
    for c in tys:
        res += c*x[c]
    if not res:
        res = "0"
    return res


class ManaPool:
    """A player's mana pool"""

    def __init__(self):
        self.pool = {c: 0 for c in mana_types}
        self.special = []

    def __getattr__(self, name):
        if name in mana_types:
            return self.pool[name]
        raise AttributeError(name)

    def __setattr__(self, name: str, value: int) -> None:
        if name in mana_types:
            self.pool[name] = value
        else:
            object.__setattr__(self, name, value)

    def __getitem__(self, name):
        return self.pool[name]

    def __setitem__(self, name, value):
        if name in self.pool:
            self.pool[name] = value
        else:
            raise KeyError(name)

    def empty(self):
        """Empties the mana pool. Effects that make certain types of mana not empty, convert, or cause mana burn are not implemented."""
        # todo: hooks for effects that affect mana emptying
        for c in self.pool:
            self.pool[c] = 0
        nspecial = []
        for s in self.special:
            if not s.should_empty() and s.amt > 0:
                nspecial.append(s)
        self.special = nspecial

    def payable_for(self, obj) -> dict:
        """Returns the total amount of mana that can be spent on obj, in the form of a dict."""
        res = {c: x for c, x in self.pool.items()}
        for s in self.special:
            if s.can_spend_on(obj):
                res[s.colour] += s.amt
        return res

    def spend(self, col, amt, obj, choices=None) -> int:
        """Attempts to spend the amount of the given colour specified on obj.
        Returns the amount of mana remaining to be spent."""
        if col == "gen":
            for c in mana_types:
                amt = self.spend(c, amt, obj, choices)
                if amt == 0:
                    return 0
            return amt
        if amt <= self.pool[col]:
            self.pool[col] -= amt
            return 0
        amt -= self.pool[col]
        self.pool[col] = 0
        for s in self.special:
            if s.colour == col and s.amt >= 0 and s.can_spend_on(obj):
                spent = min(amt, s.amt)
                amt -= spent
                s.amt -= spent
                s.on_spend(obj, spent)
            if amt == 0:
                return 0
        return amt

    def __iadd__(self, x):
        x = mana(x)
        if isinstance(x, SpecialMana):
            self.special.append(x)
        else:
            for c in x:
                self.pool[c] += x.c
        return self

    def __str__(self):
        res = mana_str(self.pool)

        if self.special:
            if res != "0":
                res += " + "
            else:
                res = ""
            for m in self.special:
                res += (int(m.amt) if m.colour ==
                        "C" else m.colour*m.amount) + "*"
        return res


@dataclass
class SpecialMana:
    """A special bit of mana that is custimizable on what it can be spent on and what happens when it is spent."""
    colour: str
    amt: int = 1

    def can_spend_on(self, src) -> bool:
        """Returns true if this mana can be spent on the given source"""
        return True

    def on_spend(self, src, amt: int):
        """Called when this mana is spent"""
        pass

    def should_empty(self):
        """Returns true if the given mana should empty from a player's mana pool"""
        return True
