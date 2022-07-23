from cgi import print_directory
from collections import defaultdict
from typing import Counter
import game
import effects
import objectsets
from game import Player

# 117.3. Which player has priority is determined by the following rules:
#    117.3a The active player receives priority at the beginning of most steps and phases, after any turn-
#    based actions (such as drawing a card during the draw step; see rule 703) have been dealt with
#    and abilities that trigger at the beginning of that phase or step have been put on the stack. No
#    player receives priority during the untap step. Players usually don’t get priority during the
#    cleanup step (see rule 514.3).
#    117.3b The active player receives priority after a spell or ability (other than a mana ability) resolves.
#    117.3c If a player has priority when they cast a spell, activate an ability, or take a special action,
#    that player receives priority afterward.
#    117.3d If a player has priority and chooses not to take any actions, that player passes. If any mana is
#    in that player’s mana pool, they announce what mana is there. Then the next player in turn order
#    receives priority
# 117.4. If all players pass in succession (that is, if all players pass without taking any actions in between
# passing), the spell or ability on top of the stack resolves or, if the stack is empty, the phase or step
# ends.
# 117.5. Each time a player would get priority, the game first performs all applicable state-based actions
# as a single event (see rule 704, “State-Based Actions”), then repeats this process until no state-based
# actions are performed. Then triggered abilities are put on the stack (see rule 603, “Handling
# Triggered Abilities”). These steps repeat in order until no further state-based actions are performed
# and no abilities trigger. Then the player who would have received priority does so.


class Step:
    """A step of a turn"""
    name: str

    def __init__(self, name=None):
        self.name = name or self.__class__.name
        self.skipped = False

    def start(self):
        """Called when this step starts"""
        turn = game.turn
        turn.give_priority(turn.active_player)

    def end(self):
        """Called when this step ends"""
        for p in game.players:
            p.mana_pool.empty()

    def __str__(self):
        return self.name


class Phase:
    """A phase of a turn"""
    name: str

    def __init__(self):
        self.steps = self.init_steps()
        self.cur_step_idx = 0

    def init_steps(self):
        """Returns the steps in this phase"""
        return []

    @property
    def step(self):
        """Gets the current step"""
        return self.steps[self.cur_step_idx]

    def next_step(self):
        """Moves to the next step"""
        self.step.end()
        while True:
            self.cur_step_idx += 1
            if self.cur_step_idx >= len(self.steps):
                return False
            if not self.step.skipped:
                self.step.start()
                return True

    def skip_step(self, name):
        """Skips each upcoming occurence of the named step"""
        for s in self.steps:
            if s.name == name:
                s.skipped = True

    def step_has_started(self, name):
        """Returns true if the step with the given name has started"""
        return any(s.name == name and not s.skipped for s in self.steps[:self.cur_step_idx+1])

    def __str__(self):
        return self.name


class Turn:
    """A turn. This class manages priority and turn based actions."""

    def __init__(self, active_player):
        self.active_player = active_player
        self.priority = active_player
        self.last_action = active_player
        self.phases = [BeginningPhase(), PrecombatMainPhase(),
                       CombatPhase(), PostcombatMainPhase(), EndPhase()]
        self.phase_idx = 0
        self.started = False
        self.finished = False

    def start(self):
        """Starts the turn"""
        if not self.started:
            self.started = True
            self.phase.step.start()

    @ property
    def phase(self) -> Phase:
        """Gets the current phase"""
        return self.phases[self.phase_idx]

    @ property
    def step(self):
        """Gets the current step"""
        return self.phase.step

    def give_priority(self, player):
        """Gives priority to the given player"""
        check_sbas()
        self.priority = player

    def next_step(self):
        """Moves to the next step of the turn"""
        if not self.phase.next_step():
            self.phase_idx += 1
            if self.phase_idx >= len(self.phases):
                self.finished = True
                return False
            self.phase.step.start()
        self.last_action = self.active_player
        return True

    def pass_priority(self):
        """Has the active player pass priority. When all players pass, the top object of the stack resolves, or the step ends."""
        next = game.next_player(self.priority)
        if next == self.last_action:
            if len(game.stack):
                top = game.stack.get_top()
                top.resolve()
                assert top.dead
                self.give_priority(self.active_player)
            else:
                self.next_step()
            self.last_action = self.active_player
        else:
            self.give_priority(next)

    def take_action(self):
        """Marks the last action as having been taken by the player with priority"""
        player = self.priority
        self.last_action = player
        self.give_priority(player)

    def apnap_order(self):
        """Yields the plerers in turn order starting from the actie player"""
        pl = self.active_player
        while True:
            yield pl
            pl = game.next_player(pl)
            if pl == self.active_player:
                return


def check_sbas():
    cont = True
    did_anything = False
    while cont:
        cont = False
        with effects.simultaneously:
            # 704.5. The state-based actions are as follows:

            for pl in list(game.players):
                # 704.5a If a player has 0 or less life, that player loses the game.
                if pl.life <= 0:
                    effects.lose_game(pl)
                # 704.5b If a player attempted to draw a card from a library with no cards in it since the last time
                # state-based actions were checked, that player loses the game.
                pass  # not yet implemented as not used in 3cb
                # 704.5c If a player has ten or more poison counters, that player loses the game. Ignore this rule in
                # Two-Headed Giant games; see rule 704.6b instead.
                if pl.counters["poison"] >= 10:
                    effects.lose_game(pl)

            # 704.5d If a token is in a zone other than the battlefield, it ceases to exist.
            # 704.5e If a copy of a spell is in a zone other than the stack, it ceases to exist. If a copy of a card is in
            # any zone other than the stack or the battlefield, it ceases to exist.

            for ob in list(game.objects):
                if isinstance(ob, game.Token) and ob.zone not in [game.battlefield, game.stack]:
                    ob.delete()

            for cr in objectsets.creatures:
                # 704.5f If a creature has toughness 0 or less, it’s put into its owner’s graveyard. Regeneration can’t
                # replace this event.
                if cr.toughness <= 0:
                    effects.move(cr, cr.owner.graveyard)
                else:
                    # 704.5g If a creature has toughness greater than 0, it has damage marked on it, and the total damage
                    # marked on it is greater than or equal to its toughness, that creature has been dealt lethal damage
                    # and is destroyed. Regeneration can replace this event.
                    if cr.permstate:
                        if cr.permstate.damage >= cr.toughness:
                            effects.destroy(cr)
                        # 704.5h If a creature has toughness greater than 0, and it’s been dealt damage by a source with
                        # deathtouch since the last time state-based actions were checked, that creature is destroyed.
                        # Regeneration can replace this event.
                        if cr.permstate.deathtouch_damage:
                            effects.destroy(cr)
                        cr.deathtouch_damage = False
            for pw in objectsets.permanents.with_type("planeswalker"):
                if not pw.counters["loyalty"]:
                    # 704.5i If a planeswalker has loyalty 0, it’s put into its owner’s graveyard.
                    effects.move(pw, pw.owner.graveyard)

            # 704.5j If a player controls two or more legendary permanents with the same name, that player
            # chooses one of them, and the rest are put into their owners’ graveyards. This is called the
            # “legend rule.”
            pass  # not yet implemented
            # 704.5k If two or more permanents have the supertype world, all except the one that has had the
            # world supertype for the shortest amount of time are put into their owners’ graveyards. In the
            # event of a tie for the shortest amount of time, all are put into their owners’ graveyards. This is
            # called the “world rule.”
            pass  # not yet impleneted
            # 704.5m If an Aura is attached to an illegal object or player, or is not attached to an object or player,
            # that Aura is put into its owner’s graveyard.
            pass  # not yet implemented
            # 704.5n If an Equipment or Fortification is attached to an illegal permanent or to a player, it becomes
            # unattached from that permanent or player. It remains on the battlefield.
            pass  # not yet implemented
            # 704.5p If a creature is attached to an object or player, it becomes unattached and remains on the
            # battlefield. Similarly, if a permanent that’s neither an Aura, an Equipment, nor a Fortification is
            # attached to an object or player, it becomes unattached and remains on the battlefield.
            pass  # not yet implemented
            # 704.5q If a permanent has both a +1/+1 counter and a -1/-1 counter on it, N +1/+1 and N -1/-1
            # counters are removed from it, where N is the smaller of the number of +1/+1 and -1/-1 counters
            # on it.
            for per in objectsets.permanents:
                n = min(per.counters["+1/+1"], per.counters["-1/-1"])
                if n > 0:
                    effects.remove_counters(per, "+1/+1", n)
                    effects.remove_counters(per, "-1/-1", n)
            # 704.5r If a permanent with an ability that says it can’t have more than N counters of a certain kind
            # on it has more than N counters of that kind on it, all but N of those counters are removed from
            # it.
            pass  # not implemented - this is literally only relevant for one card
            # 704.5s If the number of lore counters on a Saga permanent is greater than or equal to its final
            # chapter number and it isn’t the source of a chapter ability that has triggered but not yet left the
            # stack, that Saga’s controller sacrifices it. See rule 715, “Saga Cards.”
            pass  # not yet implemented
            # 704.5t If a player’s venture marker is on the bottommost room of a dungeon card, and that dungeon
            # card isn’t the source of a room ability that has triggered but not yet left the stack, the dungeon
            # card’s owner removes it from the game. See rule 309, “Dungeons.”
            pass  # not yet implemented
        # todo: check whether we did anything
        # for now we just have one pass [but we also don't have cts effects that can make multiple passes needed]


class BeginningPhase(Phase):
    name = "beginning"

    def init_steps(self):
        return [UntapStep(), Step("upkeep"), DrawStep()]

    def skip_draw(self):
        self.skip_step("draw")


class UntapStep(Step):
    name = "untap"

    def start(self):
        with effects.simultaneously:
            for perm in game.battlefield:
                if perm.controller == game.turn.active_player:
                    effects.untap(perm)
                    perm.permstate.summoning_sick = False
                perm.permstate.used_loyalty = False
        for pl in game.players:
            pl.lands_played = 0
        check_sbas()
        game.turn.next_step()


class DrawStep(Step):
    name = "draw"

    def start(self):
        game.turn.active_player.draw()
        super().start()


class MainPhase(Phase):
    name = "main"

    def init_steps(self):
        return [Step("main")]


class PrecombatMainPhase(MainPhase):
    name = "precombat main"


class PostcombatMainPhase(MainPhase):
    name = "postcombat main"


class CombatPhase(Phase):
    name = "combat"

    def __init__(self):
        super().__init__()
        self.attackers = set()
        self.blockers = set()
        self.attacks = {}
        self.attacks_blocked = {}
        self.attacks_unblocked = set()
        self.blocks = []
        self.damage_orders = {}

    def init_steps(self):
        return [Step("begin_combat"), AttackStep(), BlockStep(), DamageStep(), Step("end_combat")]

    def remove_pw_from_combat(self, pw):
        for at, df in self.attacks:
            if df == pw:
                self.attacks[at] = None

    def remove_cr_from_combat(self, cr):
        if cr in self.attacks:
            del self.attacks[cr]
        self.attackers -= {cr}
        self.attacks_blocked -= {cr}
        self.attacks_unblocked -= {cr}
        self.blocks = [(at, bl)
                       for at, bl in self.blocks if cr not in [at, bl]]
        del self.damage_orders[cr]
        for other, ord in self.damage_orders.items():
            self.damage_orders[other] = [x for x in ord if x != cr]

    def remove_from_combat(self, cr_or_pw):
        self.remove_cr_from_combat(self, cr_or_pw)
        self.remove_pw_from_combat(self, cr_or_pw)

    def legal_attackers(self, you):
        return objectsets.creatures.controlled_by(you).filter(lambda x: x.can_tap())

    def legal_attackables(self, you):
        return objectsets.players.other_than(you) | objectsets.permanents.not_controlled_by(you).with_type("planeswalker")

    def is_legal_attack_set(self, atks):
        # todo: attacking restrictions
        return True

    def enter_attacking(self, atk, df=None):
        """Has at become attacking after the attackers have been declared.
        df is the attacked player/planeswalker, or None if it can be chosen by the attacker."""
        you = game.turn.active_player
        if atk not in objectsets.creatures.controlled_by(game.turn.active_player):
            return
        if df and df not in self.legal_attackables(you):
            return
        if df is None:
            df = you.choose_objects(self.legal_attackables(
                you), reason=("attacking", atk))
        assert df in self.legal_attackables(you)
        self.attacks[atk] = df
        self.attackers.add(atk)
        if self.step_has_started("blocks"):
            self.attacks_unblocked.add(atk)

    def add_attack(self, atk, df):
        self.attacks[atk] = df
        self.attackers.add(atk)
        atk.permstate.attacked_obj = df
        atk.permstate.defending_player = df.controller

    def legal_blockers(self, def_pl):
        return objectsets.creatures.controlled_by(def_pl).is_untapped()

    def is_legal_block_set(self, def_pl, blocks):
        # todo: blocking restrictions and requirements,
        for atk, blk in blocks:
            if atk not in self.attacks:
                return False
            if atk.permstate.defending_player != def_pl:
                return False
            if blk not in self.legal_blockers(atk.permstate.defending_player):
                return False
        c = Counter(blk for atk, blk in blocks)
        for blk, n in c.items():
            if n > 1:
                # todo: allow for extra blocker effects
                return False
        return True

    def add_block(self, atk, blk):
        self.blockers.add(blk)
        self.blocks.append((atk, blk))
        self.attacks_unblocked -= {atk}


class AttackStep(Step):
    name = "attacks"

    def start(self):
        self.phase = game.turn.phase
        phase: CombatPhase = self.phase
        you = game.turn.active_player
        # 508.1. First, the active player declares attackers. This turn-based action doesn’t use the stack. To
        # declare attackers, the active player follows the steps below, in order. If at any point during the
        # declaration of attackers, the active player is unable to comply with any of the steps listed below, the
        # declaration is illegal; the game returns to the moment before the declaration (see rule 726,
        # “Handling Illegal Actions”).

        # we just throw AssertionError on illegal actions; unless they have a simple fix like ignoring it before any gamestate has been commited

        #     508.1a The active player chooses which creatures that they control, if any, will attack. The chosen
        #     creatures must be untapped, and each one must either have haste or have been controlled by the
        #     active player continuously since the turn began.

        #     508.1b If the defending player controls any planeswalkers, or the game allows the active player to
        #     attack multiple other players, the active player announces which player or planeswalker each of
        #     the chosen creatures is attacking.

        atks = you.decide_attacks()
        if atks == None:
            atks = {}
        if type(atks) == list:
            datks = {}
            for atk in atks:
                datks[atk] = game.next_player(you)
            atks = datks
        atks = {at: df for (at, df) in atks.items()
                if at in phase.legal_attackers(you) and df in phase.legal_attackables(you)}  # silently ignore bad attacks

        #     508.1c The active player checks each creature they control to see whether it’s affected by any
        #     restrictions [...]

        #     508.1d The active player checks each creature they control to see whether it’s affected by any
        #     requirements [...]

        assert phase.is_legal_attack_set(atks)

        #     508.1e If any of the chosen creatures have banding or a “bands with other” ability, the active player
        #     announces which creatures, if any, are banded with which. (See rule 702.22, “Banding.”)

        # banding is not yet implemented

        with effects.simultaneously:
            for atk in atks:
                #     508.1f The active player taps the chosen creatures. Tapping a creature when it’s declared as an
                #     attacker isn’t a cost; attacking simply causes creatures to become tapped.

                if not atk.has_keyword("vigilance"):
                    effects.tap(atk)

        #     508.1g If there are any optional costs to attack with the chosen creatures (expressed as costs a
        #     player may pay “as” a creature attacks), the active player chooses which, if any, they will pay.

        #     508.1h If any of the chosen creatures require paying costs to attack, or if any optional costs to attack
        #     were chosen, the active player determines the total cost to attack. Costs may include paying
        #     mana, tapping permanents, sacrificing permanents, discarding cards, and so on. Once the total
        #     cost is determined, it becomes “locked in.” If effects would change the total cost after this time,
        #     ignore this change.

        #     508.1i If any of the costs require mana, the active player then has a chance to activate mana abilities
        #     (see rule 605, “Mana Abilities”).

        #     508.1j Once the player has enough mana in their mana pool, they pay all costs in any order. Partial
        #     payments are not allowed.

        # costs are not yet implemnted
        # also, looks like all optional costs are exert
        # in fact, costs to attack/block *require* mana ability timing

        #     508.1k Each chosen creature still controlled by the active player becomes an attacking creature. It
        #     remains an attacking creature until it’s removed from combat or the combat phase ends,
        #     whichever comes first. See rule 506.4.

        for atk, df in atks.items():
            phase.add_attack(atk, df)

        #     508.1m Any abilities that trigger on attackers being declared trigger.

        # triggered abilities are not yet implemented

        # todo: attacking requirements/restrictions, additional costs, triggered abilities

        # 508.2. Second, the active player gets priority.
        super().start()

    def end(self):
        phase = self.phase
        if not phase.attackers:
            phase.skip_step("blocks")
            phase.skip_step("damage")


class BlockStep(Step):
    name = "blocks"

    def start(self):
        self.phase = game.turn.phase
        phase: CombatPhase = self.phase
        phase.attacks_unblocked = set(phase.attackers)
        dfs = defaultdict(dict)

        for atk, df in phase.attacks.items():
            dfs[df.controller][atk] = df

        # 509.1. First, the defending player declares blockers. This turn-based action doesn’t use the stack. To
        # declare blockers, the defending player follows the steps below, in order. If at any point during the
        # declaration of blockers, the defending player is unable to comply with any of the steps listed below,
        # the declaration is illegal; the game returns to the moment before the declaration (see rule 727,
        # “Handling Illegal Actions”).

        for def_pl in game.turn.apnap_order():
            atks = dfs[def_pl]
            if atks:

                #     509.1a The defending player chooses which creatures they control, if any, will block. The chosen
                #     creatures must be untapped. For each of the chosen creatures, the defending player chooses one
                #     creature for it to block that’s attacking that player or a planeswalker they control.

                blocks = def_pl.decide_blocks(atks)
                if not blocks:
                    blocks = []

                #     509.1b The defending player checks each creature they control to see whether it’s affected by any
                #     restrictions [...]

                #     509.1c The defending player checks each creature they control to see whether it’s affected by any
                #     requirements [...]

                assert phase.is_legal_block_set(def_pl, blocks)

                #     509.1d If any of the chosen creatures require paying costs to block, the defending player determines
                #     the total cost to block. Costs may include paying mana, tapping permanents, sacrificing
                #     permanents, discarding cards, and so on. Once the total cost is determined, it becomes “locked
                #     in.” If effects would change the total cost after this time, ignore this change.

                #     509.1e If any of the costs require mana, the defending player then has a chance to activate mana
                #     abilities (see rule 605, “Mana Abilities”).

                #     509.1f Once the player has enough mana in their mana pool, they pay all costs in any order. Partial
                #     payments are not allowed.

                # costs are not implemented

                #     509.1g Each chosen creature still controlled by the defending player becomes a blocking creature.
                #     Each one is blocking the attacking creatures chosen for it. It remains a blocking creature until
                #     it’s removed from combat or the combat phase ends, whichever comes first. See rule 506.4.

                #     509.1h An attacking creature with one or more creatures declared as blockers for it becomes a
                #     blocked creature; one with no creatures declared as blockers for it becomes an unblocked
                #     creature. This remains unchanged until the creature is removed from combat, an effect says that
                #     it becomes blocked or unblocked, or the combat phase ends, whichever comes first. A creature
                #     remains blocked even if all the creatures blocking it are removed from combat.

                for atk, blk in blocks:
                    phase.add_block(atk, blk)

        #     509.1i Any abilities that trigger on blockers being declared trigger. See rule 509.4 for more
        #     information.

        # triggered abilities are not yet implemented

        # 509.2. Second, for each attacking creature that’s become blocked, the active player announces that
        # creature’s damage assignment order, which consists of the creatures blocking it in an order of that
        # player’s choice. (During the combat damage step, an attacking creature can’t assign combat damage
        # to a creature that’s blocking it unless each creature ahead of that blocking creature in its order is
        # assigned lethal damage.) This turn-based action doesn’t use the stack.

        # 509.3. Third, for each blocking creature, the defending player announces that creature’s damage
        # assignment order, which consists of the creatures it’s blocking in an order of that player’s choice.
        # (During the combat damage step, a blocking creature can’t assign combat damage to a creature it’s
        # blocking unless each creature ahead of that blocked creature in its order is assigned lethal damage.)
        # This turn-based action doesn’t use the stack.

        orders = defaultdict(list)
        for atk, blk in phase.blocks:
            orders[atk].append(blk)
            orders[blk].append(atk)

        for pl in game.turn.apnap_order():
            # first will be the active player; then the defending players in the correct order
            for cr, dmg in orders.items():
                if cr.controller == pl:
                    if len(dmg) <= 1 or (ord := pl.decide_order(dmg, ("combat", cr))) == None:
                        phase.damage_orders[cr] = dmg
                    else:
                        assert sorted(dmg, key=id) == sorted(ord, key=id)
                        phase.damage_orders[cr] = ord

        # 509.4. Fourth, the active player gets priority. (See rule 117, “Timing and Priority.”)

        # todo: restrictions/requirements/costs for blocking, triggered abilities

        super().start()


class DamageStep(Step):
    name = "damage"

    def __init__(self, already_damaged=None):
        super().__init__()
        self.already_damaged = already_damaged

    def start(self):
        # todo: annotate with rules
        phase = game.turn.phase
        assert isinstance(phase, CombatPhase)

        in_combat = phase.attackers | phase.blockers

        if not self.already_damaged:
            to_damage = []
            for cr in in_combat:
                if cr.has_keyword("first strike") or cr.has_keyword("double strike"):
                    to_damage.append(cr)
            if to_damage:
                phase.steps.insert(phase.cur_step_idx+1, DamageStep(True))
            else:
                to_damage = list(in_combat)
        else:
            to_damage = []
            for cr in in_combat:
                if cr not in self.already_damaged or cr.has_keyword("double strike"):
                    to_damage.append(cr)

        overall_assign = []
        for pl in game.turn.apnap_order():
            my_orders = {}
            for cr in to_damage:
                if cr.controller == pl and cr.power > 0:
                    if cr in phase.attacks_unblocked and phase.attacks[cr]:
                        my_orders[cr] = [phase.attacks[cr]]
                    else:
                        ord = phase.damage_orders.get(cr, [])
                        if cr in phase.attackers and phase.attacks[cr] and cr.has_keyword("trample"):
                            # todo: trample over pws
                            # also is this correct for a cr pw blocking an attack to itself?
                            ord = ord + [phase.attacks[cr]]
                        if ord:
                            my_orders[cr] = ord
            # todo: split assignment into independent parts
            if self.one_possible_assignment(my_orders) or ((assign := pl.decide_damage(my_orders)) == None):
                assign = self.default_assignment(my_orders)
            assert self.is_legal_assignment(assign, my_orders)
            print(f"{pl=}, {my_orders=}, {assign=}")
            overall_assign += assign

        with effects.simultaneously:
            for src, target, amt in overall_assign:
                effects.damage(src, target, amt, combat=True)

        super().start()

    @staticmethod
    def one_possible_assignment(orders):
        for src, ord in orders.items():
            if len(ord) >= 2:
                if src.power > DamageStep.remaining_damage(ord[0], src):
                    return False
                if any(ord[0] in ord2 for (src2, ord2) in orders.items() if src2 != src):
                    return False
        return True

    @staticmethod
    def remaining_damage(cr, src=None):
        dmg = max(cr.toughness - cr.permstate.damage, 0)
        if src == None:
            return dmg
        if type(src) == bool:
            dt = src
        else:
            dt = src.has_keyword("deathtouch")
        if dt:
            return min(dmg, 1)
        else:
            return dmg

    @staticmethod
    def default_assignment(orders):
        assign = []
        for src, ord in orders.items():
            dt = src.has_keyword("deathtouch")
            pow = src.power
            for target in ord[:-1]:
                if pow <= 0:
                    break
                lethal = DamageStep.remaining_damage(target, dt)
                assign.append((src, target, min(lethal, pow)))
                pow -= lethal
            if pow > 0:
                assign.append((src, ord[-1], pow))
        return assign

    @staticmethod
    def is_legal_assignment(assign, orders):
        totals_dealt = Counter()
        totals_received = Counter()

        for (src, target, amt) in assign:
            if src not in orders or target not in orders[src] or amt < 0:
                return False

            totals_dealt[src] += amt
            totals_received[target] += amt

        for src in orders:
            if totals_dealt[src] != src.power:
                return False

        lethals = set()
        for target, amt in totals_received.items():
            if target.has_type("creature") and amt >= DamageStep.remaining_damage(target):
                lethals.add(target)
        for src, target, amt in assign:
            if src.has_keyword("deathtouch") and amt > 0:
                lethals.add(target)

        for src, target, amt in assign:
            if amt > 0:
                for target2 in orders[src]:
                    if target2 == target:
                        break
                    if target2 not in lethals:
                        return False

        return True


class EndPhase(Phase):
    name = "end"

    def init_steps(self):
        return [Step("end"), Step("cleanup")]
