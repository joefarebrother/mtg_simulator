
from typing import Optional
from abilities import ActivatedAbility
from actions import PlayCard, ActivateAbility, Action
from game import Player
import game
import objectsets
import turn


def print_board():
    """Displays the current board state in a human friendly way"""
    def print_player(p, rev):
        lines = []
        lines.append(f"{p.name} [id={p.id}] life: {p.life}")
        lines.append(f"Hand: {list(p.hand)}")
        lines.append(f"Graveyard: {list(p.graveyard)}")
        lines.append(f"Library: {len(p.library)} cards")
        lines.append(f"Mana: {p.mana_pool}")
        lands = []
        nonlands = []
        for perm in game.battlefield:
            if perm.controller == p:
                if perm.types == ["land"]:
                    lands.append(perm)
                else:
                    nonlands.append(perm)
        lines.append(str(lands))
        lines.append(str(nonlands))
        lines.append("")

        if rev:
            lines = lines[::-1]

        for l in lines:
            print(l)

    print_player(game.players[1], False)
    print(f"{' '*20}Stack: {list(game.stack)}")
    print_player(game.players[0], True)
    print()

    print()
    print(
        f"Phase: {game.turn.phase}, Step: {game.turn.step}, Turn: {game.turn_idx}")
    print(
        f"Active player: {game.turn.active_player.name}, Priority: {game.turn.priority.name}, Last action: {game.turn.last_action}")
    if isinstance((phase := game.turn.phase), turn.CombatPhase):
        if phase.step_has_started("attacks"):
            print("Attacks:", phase.attacks)
        if phase.step_has_started("blocks"):
            print("Blocks:", phase.blocks)
            print("Damage orders:", phase.damage_orders)
    print()


class Goldfish(Player):
    """A player that will take no actions and always make the default choices"""

    def __init__(self, name: str, verbose=False):
        super().__init__(name)
        self.verbose = verbose

    def decide_action(self):
        if self.verbose:
            print_board()
        return None


class UserPlayer(Player):
    """A player controlled by the user"""

    def __init__(self, name: str):
        super().__init__(name)
        self.f6d_until = None

    def decide_action(self):
        print_board()
        if self.f6d_until:
            t, phase = self.f6d_until
            if game.turn_idx < t or (game.turn_idx == t and phase not in [game.turn.phase.name, game.turn.phase.step.name]):
                return None
            self.f6d_until = None
        while True:
            try:
                inp = input("> ")
                if inp.startswith("!"):
                    try:
                        print(eval(inp[1:]))
                    except:
                        import traceback
                        traceback.print_exc()
                    continue
                inp = inp.split()
                if len(inp) == 0:
                    return None
                if inp[0] in ["cast", "play", "p"] and len(inp) > 1:
                    i = int(inp[1])
                    return PlayCard(game.objects[i])
                if inp[0] in ["activate", "a"] and len(inp) > 1:
                    i = int(inp[1])
                    src = game.objects[i]
                    abs = [ab for ab in src.abilities if isinstance(
                        ab, ActivatedAbility)]
                    if len(abs) > 0 and len(inp) > 2:
                        ab = abs[int(inp[2])]
                    else:
                        ab = abs[0]
                    return ActivateAbility(ab)
                if inp[0] in ["details", "d"]:
                    ob = game.objects[int(inp[1])]
                    print(ob)
                    print(f"Zone: {ob.zone}")
                    print(f"Chars: {ob.chars}")
                    if ob.permstate:
                        print(f"State: {ob.permstate}")
                    print(f"Counters: {ob.counters}")
                    if ob.spell_choices:
                        print(f"Choices: {ob.spell_choices}")
                if inp[0] in ["b", "board"]:
                    print_board()
                if inp[0] == "f6":
                    _, t, ph = (inp+[None]*2)[:3]
                    if not t:
                        self.f6d_until = (game.turn_idx+1, "upkeep")
                    elif ph:
                        self.f6d_until = (int(t), ph)
                    else:
                        try:
                            t = int(t)
                            self.f6d_until = (t, "upkeep")
                        except ValueError:
                            self.f6d_until = (game.turn_idx+1, t)
                    return None
                if inp[0] == "locator":
                    self.use_tournament_locator()

            except (ValueError, IndexError, KeyError):
                pass

    def decide_objects(self, obs: objectsets.ObjectSet, reason=None, min: int = 1, max: int = None, order_matters=False):
        if max == None:
            max = min
        rng = f"{min}-{max}" if min != max else str(min)
        plr = 's'*(max > 1)
        print(f"Choose {rng} object{plr} from among {[ob.id for ob in obs]}")
        if type(reason) == tuple:
            if reason[0] == "target":
                print(f"(Target{plr} for {reason[1]})")
            else:
                print(reason)
        while True:
            try:
                inp = input("> ").split()
                ch = [game.objects[int(i)] for i in inp]
                if min <= len(ch) == len(set(ch)) <= max and all(c in obs for c in ch):
                    return ch
            except (ValueError, KeyError):
                pass

    def decide_attacks(self):
        phase = game.turn.phase
        assert isinstance(phase, turn.CombatPhase) and isinstance(
            phase.step, turn.AttackStep)
        if not phase.legal_attackers(self):
            return None
        atks = {}
        print_board()
        print("Declare attacks: ")
        while True:
            print(atks)
            try:
                inp = input("> ")
                inp = inp.split()
                if len(inp) == 0:
                    if not phase.is_legal_attack_set(atks):
                        print("Illegal attacks")
                        continue
                    else:
                        return atks
                cr = game.objects[int(inp[0])]
                if cr not in phase.legal_attackers(self):
                    print("Illegal attacker")
                    continue
                if len(inp) == 1:
                    if cr in atks:
                        del atks[cr]
                    else:
                        atks[cr] = game.next_player(self)
                    continue
                df = game.objects[int(inp[1])]
                if df not in phase.legal_attackables(self):
                    print("Illegal defender")
                    continue
                atks[cr] = df
            except (KeyError, ValueError):
                pass

    def decide_blocks(self, atks: dict) -> list:
        phase = game.turn.phase
        assert isinstance(phase, turn.CombatPhase) and isinstance(
            phase.step, turn.BlockStep)
        if not phase.legal_blockers(self):
            return None
        print_board()
        print(f"Attacks: {atks}; Declare blockers:")
        blks = []
        while True:
            print(blks)
            try:
                inp = input("> ")
                inp = [int(x) for x in inp.split()]
                if len(inp) == 0:
                    if not phase.is_legal_block_set(self, blks):
                        print("Illegal blocks")
                        continue
                    else:
                        return blks
                if len(inp) == 1:
                    if len(atks) == 1:
                        blk = game.objects[inp[0]]
                        atk = next(iter(atks))
                    else:
                        print("Must specify attacker and blocker")
                        continue
                if len(inp) == 2:
                    atk, blk = inp
                    atk, blk = game.objects[atk], game.objects[blk]
                    if atk not in atks and blk in atks:
                        atk, blk = blk, atk
                if atk not in atks or blk not in phase.legal_blockers(self):
                    print("Illegal block")
                    continue
                # todo: check single block validity e.g. for flying
                if (atk, blk) in blks:
                    blks = [x for x in blks if x != (atk, blk)]
                else:
                    blks.append((atk, blk))

            except (KeyError, ValueError):
                pass


class PlayCards(Player):
    """A player that will always try to play any cards and activate any abilities it can during its main phase"""

    def decide_action(self) -> Optional[Action]:
        if not isinstance(game.turn.phase, turn.MainPhase):
            return None

        for card in game.objects.values():
            act = PlayCard(card)
            if act.can_take_action(self, None):
                return act
            for ab in card.abilities:
                if isinstance(ab, ActivatedAbility):
                    act = ActivateAbility(ab)
                    if act.can_take_action(self, None):
                        return act

        return None


class Aggressive(PlayCards):
    """A player that always attacks"""

    def decide_attacks(self):
        return list(game.turn.phase.legal_attackers(self))
