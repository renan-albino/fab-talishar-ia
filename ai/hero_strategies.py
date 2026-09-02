"""
Estratégias especializadas por classe e herói de Flesh and Blood.
Avaliação de cartas de ataque, pitch, bloqueio e mecânicas específicas (Boost, Crank, etc.).
"""

import re
from functools import lru_cache

class HeroStrategy:
    def __init__(self, hero_name: str = "generic"):
        self.hero_name = str(hero_name).lower()

    @lru_cache(maxsize=1024)
    def evaluate_attack_card(self, card_name: str, power: int, cost: int, has_go_again: bool, pitch: int) -> float:
        """Calcula score de prioridade de ataque na cadeia de combate."""
        score = float(power)
        if has_go_again:
            score += 4.0
        score -= cost * 0.5
        if pitch == 1:
            score += 2.0
        elif pitch == 3:
            score -= 1.0
        return score

    @lru_cache(maxsize=1024)
    def evaluate_pitch_card(self, card_name: str, pitch: int, cost: int, power: int, has_go_again: bool) -> float:
        """Calcula score para escolher qual carta dar Pitch (Pitch 3 > Pitch 2 > Pitch 1)."""
        score = float(pitch) * 4.0
        # Penaliza dar pitch em cartas de alto valor de ataque com go again
        if power >= 4:
            score -= 2.0
        if has_go_again:
            score -= 2.0
        if pitch == 1:
            score -= 3.0
        return score

    def evaluate_card_priority(self, card_name: str, cost: int, pitch: int, power: int, has_go_again: bool) -> float:
        return self.evaluate_attack_card(card_name, power, cost, has_go_again, pitch)

    def should_boost(self, card_name: str, hand_size: int, deck_size: int) -> bool:
        return deck_size > 5

    def should_crank(self, item_name: str, has_actions_left: bool) -> bool:
        return True

    @lru_cache(maxsize=1024)
    def evaluate_block_card(self, card_name: str, block_val: int, pitch: int, power: int, has_go_again: bool) -> float:
        if block_val <= 0:
            return -999.0
        offensive_value = power + (3.0 if has_go_again else 0.0)
        block_score = float(block_val) * 2.0 - offensive_value
        return block_score

    def evaluate_arsenal_card(self, card_info: dict, db_entry: dict = None) -> float:
        """Calcula score de utilidade para colocar carta no Arsenal no fim do turno."""
        c_name = card_info.get("name", "").lower()
        pitch = card_info.get("pitch", 1)
        power = card_info.get("power", 0)
        card_type = (db_entry.get("type", "") if db_entry else "").upper()
        subtype = (db_entry.get("subtype", "") if db_entry else "").lower()

        # Poda estrita universal: tipo R (Resource) ou Gem NUNCA vai para o Arsenal!
        # Regra FaB CR 3.1.5: Arsenal não dá pitch e Recursos não podem ser jogados como ação/defesa.
        if card_type == "R" or "gem" in subtype or any(k in c_name for k in [
            "riches_of_tropal", "heart_of_fyendal", "eye_of_ophidia",
            "grandeur_of_valahai", "arknight_shard", "fools_gold",
            "cracked_bauble", "cracker_bauble", "inner_chi"
        ]):
            return -9999.0

        score = float(power)
        if pitch == 1:
            score += 5.0
        elif pitch == 3:
            score -= 6.0

        if card_info.get("has_go_again", False):
            score += 2.0
        if card_info.get("cost", 0) == 0:
            score += 1.5

        # Reações de Defesa e Instants são ótimos no Arsenal
        if card_type in ("DR", "I") or any(k in c_name for k in ["sink_below", "fate_foreseen", "sigil", "oasis"]):
            score += 4.0

        return score


class MechanologistStrategy(HeroStrategy):
    @lru_cache(maxsize=1024)
    def evaluate_attack_card(self, card_name: str, power: int, cost: int, has_go_again: bool, pitch: int) -> float:
        score = super().evaluate_attack_card(card_name, power, cost, has_go_again, pitch)
        c_low = card_name.lower()
        if "zero_to_sixty" in c_low or "zipper" in c_low:
            score += 2.0
        elif "throttle" in c_low or "fast_and_furious" in c_low:
            score += 1.5
        return score

    def should_boost(self, card_name: str, hand_size: int, deck_size: int) -> bool:
        return deck_size > 6

    def should_crank(self, item_name: str, has_actions_left: bool) -> bool:
        return True


class NinjaStrategy(HeroStrategy):
    @lru_cache(maxsize=1024)
    def evaluate_attack_card(self, card_name: str, power: int, cost: int, has_go_again: bool, pitch: int) -> float:
        score = super().evaluate_attack_card(card_name, power, cost, has_go_again, pitch)
        c_low = card_name.lower()
        if "surge" in c_low or "leg_tap" in c_low or "rising_knee" in c_low:
            score += 3.0
        if "kodachi" in c_low:
            score += 1.5
        return score


class WizardStrategy(HeroStrategy):
    @lru_cache(maxsize=1024)
    def evaluate_attack_card(self, card_name: str, power: int, cost: int, has_go_again: bool, pitch: int) -> float:
        score = super().evaluate_attack_card(card_name, power, cost, has_go_again, pitch)
        c_low = card_name.lower()
        if "sonic_boom" in c_low or "zap" in c_low or "aether" in c_low:
            score += 2.5
        return score


class GuardianStrategy(HeroStrategy):
    @lru_cache(maxsize=1024)
    def evaluate_attack_card(self, card_name: str, power: int, cost: int, has_go_again: bool, pitch: int) -> float:
        score = float(power)
        c_low = card_name.lower()
        # Bônus para efeitos esmagadores / on-hits pesados de Guardião
        if any(w in c_low for w in ["crush", "wager", "overpower", "bet_big", "spinal", "crippling", "buckling", "macho", "pulverize", "star_struck", "anothos", "thunderquake", "chokeslam", "cartilage"]):
            score += 5.0
        if pitch == 1 and power >= 7:
            score += 3.0
        return score

    @lru_cache(maxsize=1024)
    def evaluate_block_card(self, card_name: str, block_val: int, pitch: int, power: int, has_go_again: bool) -> float:
        if block_val <= 0:
            return -999.0
        c_low = card_name.lower()
        # Se for carta de ataque principal pesada (Vermelha de alto poder/Crush/Wager), penaliza bloquear para preservar para o Pivot
        if pitch == 1 and power >= 6:
            return -15.0
        # Cartas azuis de bloqueio 3 com alto pitch são boas para defesa
        if pitch == 3 and block_val >= 3:
            return 8.0
        return float(block_val) * 2.0 - power


class RangerStrategy(HeroStrategy):
    """
    Estratégia especializada para Rangers (Marlinn, Marlynn, Azalea, Riptide, Lexi).
    Foco de FaB:
      - Flechas (Arrows) são o centro da ofensiva e SÓ podem ser jogadas do Arsenal.
      - Cartas de Recurso (R) ou Gemas NUNCA podem ir para o Arsenal (travam o slot).
      - Prioridade de Arsenal: Flechas Vermelhas > Flechas Amarelas > Buffs > Traps > Flechas Azuis.
      - Cartas azuis de pitch puro devem ficar na mão para pagar o custo do arco.
    """
    @lru_cache(maxsize=1024)
    def evaluate_attack_card(self, card_name: str, power: int, cost: int, has_go_again: bool, pitch: int) -> float:
        score = float(power)
        c_low = card_name.lower()
        if any(k in c_low for k in ["arrow", "harpoon", "bolt", "trophy", "scoundrel", "rabble"]):
            score += 3.0
        if has_go_again:
            score += 4.0
        score -= cost * 0.5
        if pitch == 1:
            score += 2.0
        return score

    def evaluate_arsenal_card(self, card_info: dict, db_entry: dict = None) -> float:
        c_name = card_info.get("name", "").lower()
        pitch = card_info.get("pitch", 1)
        power = card_info.get("power", 0)
        subtype = (db_entry.get("subtype", "") if db_entry else "").lower()
        card_type = (db_entry.get("type", "") if db_entry else "").upper()

        # 1. PODA ABSOLUTA: Recursos e Gemas são estritamente proibidos no Arsenal!
        if card_type == "R" or "gem" in subtype or any(k in c_name for k in [
            "riches_of_tropal", "heart_of_fyendal", "eye_of_ophidia",
            "grandeur_of_valahai", "arknight_shard", "fools_gold",
            "cracked_bauble", "cracker_bauble", "inner_chi"
        ]):
            return -9999.0

        score = 0.0

        # 2. Flechas (Arrows): Prioridade #1 absoluta do Ranger
        # Regra oficial: Flechas NÃO podem ser jogadas da mão, APENAS do Arsenal com um arco
        is_arrow = "arrow" in subtype or any(k in c_name for k in ["arrow", "harpoon", "bolt", "trophy_shot", "endless_arrow"])
        if is_arrow:
            score += 15.0
            if pitch == 1:
                score += 5.0  # Flecha vermelha: melhor carta do turno seguinte
            elif pitch == 2:
                score += 2.0
            score += float(power) * 0.5
            return score

        # 3. Buffs de ataque / Ações Não-Ataque de Ranger (ex: Three of a Kind, Rain Razors, Take Aim, Codex)
        if any(k in c_name for k in ["three_of_a_kind", "rain_razors", "take_aim", "seek_horizon", "premeditation", "codex"]):
            score += 8.0
            if pitch == 1:
                score += 2.0
            return score

        # 4. Armadilhas e Reações de Defesa (Traps / Defense Reactions)
        if "trap" in subtype or card_type == "DR" or any(k in c_name for k in ["trap", "sink_below", "fate_foreseen", "shelter"]):
            score += 7.0
            return score

        # 5. Outras cartas jogáveis de ataque
        if power > 0 and pitch == 1:
            score += 4.0

        # 6. Cartas azuis de pitch puro: o Ranger precisa delas na mão para pagar o arco!
        if pitch == 3:
            score -= 10.0

        return score


@lru_cache(maxsize=128)
def get_hero_strategy(hero_name: str) -> HeroStrategy:
    h = str(hero_name).lower()
    if any(m in h for m in ["dash", "maxx", "data_doll", "mechanologist"]):
        return MechanologistStrategy(h)
    elif any(r in h for r in ["marlinn", "marlynn", "azalea", "riptide", "lexi", "ranger"]):
        return RangerStrategy(h)
    elif any(n in h for n in ["ira", "katsu", "fai", "zen", "benji", "ninja"]):
        return NinjaStrategy(h)
    elif any(w in h for w in ["kano", "iyslander", "oscilio", "wizard"]):
        return WizardStrategy(h)
    elif any(g in h for g in ["betsy", "bravo", "victor", "valda", "guardian", "rhinar", "kayo", "levia", "brute"]):
        return GuardianStrategy(h)
    return HeroStrategy(h)
