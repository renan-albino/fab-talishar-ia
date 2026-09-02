"""
ai/hero_strategies.py
======================
Estratégias especializadas por classe e herói de Flesh and Blood.
Mapeamento canônico de todos os 139 heróis oficiais e arquétipos de classe.

Classes implementadas:
  - HeroStrategy (Base universal)
  - GuardianStrategy (Crush, Overpower, Wager, 3-block value, Pivot Line, Hammer swings)
  - JarlStrategy (Guardião Elemental de Terra e Gelo, Frostbite, Oaken Old, Boulder Drop)
  - BruteStrategy (Poder 6+, Intimidate, Beat Chest, descarte, Pivot ofensivo)
  - WarriorStrategy (Foco central em ataques de arma, Reprise, retenção de reações na mão)
  - NinjaStrategy (Combos, Go Again sequencing, starters de custo 0, Kodachi)
  - RangerStrategy (Disparo prioritário do Arsenal, Poda estrita de Recursos/Gemas, LoadArrow)
  - MechanologistStrategy (Gestão de Boost com proteção contra fadiga, Crank, Scrap, Evo)
  - RunebladeStrategy (Dano misto Físico/Arcano, Runechants, sequenciamento NAA -> AA)
  - WizardStrategy (Dano arcano, velocidade Instant, altíssima demanda por pitch azul 3)
  - IllusionistStrategy (Phantasm, Heralds, Dragons, Auras, Spectral Shields, Ward)
  - AssassinStrategy (Stealth, Contratos de banimento, Adagas com Piercing, reações)
  - MerchantStrategy (Gerenciamento de moedas Gold/Silver, utilidade)
"""

import os
import re
import json
from functools import lru_cache
from typing import Optional, Dict, Any

_FAB_CARDS_DB = None

def _get_cards_db() -> dict:
    global _FAB_CARDS_DB
    if _FAB_CARDS_DB is None:
        db_paths = [
            "data/fab_cards_db.json",
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "fab_cards_db.json")
        ]
        for p in db_paths:
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        _FAB_CARDS_DB = json.load(f)
                    break
                except Exception:
                    pass
        if _FAB_CARDS_DB is None:
            _FAB_CARDS_DB = {}
    return _FAB_CARDS_DB

def is_resource_or_gem_card(card_name: str, card_info: dict = None, db_entry: dict = None) -> bool:
    """
    Verificação global universal de Flesh and Blood (CR 3.1.5):
    Recursos e Gemas NUNCA podem ser colocados no Arsenal por NENHUM herói de NENHUMA classe.
    Arsenal não dá pitch e cartas de Recurso não podem ser jogadas como ação/defesa.
    """
    c_low = str(card_name).lower()
    card_type = (db_entry.get("type", "") if db_entry else "").upper()
    subtype = (db_entry.get("subtype", "") if db_entry else "").lower()

    if card_type in ("R", "RESOURCE") or "gem" in subtype:
        return True

    # Gemas e recursos lendários/conhecidos de Flesh and Blood
    if any(k in c_low for k in [
        "riches_of_tropal", "heart_of_fyendal", "eye_of_ophidia",
        "grandeur_of_valahai", "arknight_shard", "fools_gold",
        "cracked_bauble", "cracker_bauble", "inner_chi",
        "copper", "silver", "gold_token"
    ]):
        return True

    return False


KNOWN_AMBUSH_CARDS = {
    "down_and_dirty_red", "down_and_dirty",
    "stadium_security_red", "stadium_security_yellow", "stadium_security_blue",
    "no_hero_stands_alone_yellow", "overcrowded_blue",
    "tiger_eye_reflex_yellow", "tiger_eye_reflex_blue",
}


# ══════════════════════════════════════════════════════════════════
# CLASSE BASE: HeroStrategy
# ══════════════════════════════════════════════════════════════════

class HeroStrategy:
    """Estratégia base genérica para heróis de Flesh and Blood."""
    is_heavy_hero: bool = False

    def __init__(self, hero_name: str = "generic"):
        self.hero_name = str(hero_name).lower().strip()

    def has_heavy_attack(self, card_info: dict) -> bool:
        """Determina se uma carta é um ataque pesado que justifica linha de Pivot."""
        return False

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
        return float(block_val) * 2.0 - offensive_value

    def evaluate_weapon_attack(self, card_name: str, floating_res: int, total_res: int, has_hand_attacks: bool) -> float:
        """Pontuação tática para atacar com a arma equipada."""
        score = 3.0 + (2.0 if floating_res >= 1 else 0.0)
        if not has_hand_attacks:
            score += 2.5
        return score

    def evaluate_arsenal_card(self, card_info: dict, db_entry: dict = None) -> float:
        """
        Calcula score de utilidade para colocar carta no Arsenal no fim do turno.
        
        Regras Globais de FaB (CR 3.1.5):
          1. Recursos e Gemas são normalmente proibidos no Arsenal (-9999.0).
          2. Cartas com Ambush ou Down and Dirty têm permissão de defender do Arsenal e ganham vantagem (+9.0 a +12.0).
          3. Reações de Defesa (DR) e Traps podem ser jogadas do Arsenal (+7.0 a +9.0).
          4. Cartas de ação comuns com alto valor de bloqueio (block >= 3) que NÃO têm Ambush nem são DR:
             Perdem 100% do seu valor defensivo no Arsenal e devem ficar na mão para defender (-8.0 a -14.0).
        """
        c_name = card_info.get("name", "").lower()
        pitch = card_info.get("pitch", 1)
        power = card_info.get("power", 0)
        block_val = card_info.get("block", 0)
        subtype = (card_info.get("subtype") or (db_entry.get("subtype", "") if db_entry else "")).lower()
        card_type = (card_info.get("type") or (db_entry.get("type", "") if db_entry else "")).upper()
        card_text = (card_info.get("text") or (db_entry.get("text", "") if db_entry else "")).lower()

        # 1. Poda estrita universal: tipo R (Resource) ou Gem NUNCA vai para o Arsenal!
        if is_resource_or_gem_card(c_name, card_info, db_entry):
            return -9999.0

        score = float(power)

        # 2. Exceções com Vantagem no Arsenal: Ambush e Down and Dirty
        is_down_and_dirty = "down_and_dirty" in c_name or "down and dirty" in c_name
        has_ambush = (
            c_name in KNOWN_AMBUSH_CARDS
            or any(k in c_name for k in ["stadium_security", "down_and_dirty", "no_hero_stands_alone", "overcrowded", "tiger_eye_reflex"])
            or "ambush" in subtype
            or "ambush" in card_text
            or "defend with this from your arsenal" in card_text
            or "ambush" in c_name
            or is_down_and_dirty
        )

        is_defense_reaction = (
            card_type == "DR"
            or "defense reaction" in subtype
            or "trap" in subtype
            or any(k in c_name for k in ["sink_below", "fate_foreseen", "staunch", "unmovable", "shelter", "take_cover"])
        )

        if is_down_and_dirty:
            # Down and Dirty: Ganha +1 defesa quando defende do arsenal (+12.0)
            score += 12.0
            if pitch == 1:
                score += 3.0
            return score
        elif has_ambush:
            # Ambush (ataques ou blocos): Permite defender do Arsenal, liberando o slot (+9.0)
            score += 9.0
            if block_val >= 3:
                score += 3.0
            return score
        elif is_defense_reaction:
            # Reações de Defesa e Traps são jogáveis na reaction step do Arsenal (+7.0)
            score += 7.0
            if card_info.get("cost", 0) <= 1:
                score += 2.0
        else:
            # Cartas de ação comuns com alto valor de bloqueio que NÃO são DR nem Ambush:
            # Se forem para o Arsenal, perdem toda a capacidade de defender! Devem ficar na mão.
            if block_val >= 3:
                score -= 8.0
                if power <= 3:
                    score -= 6.0  # Cartas de defesa pura ou com baixo ataque -> garantidamente negativo
            elif block_val == 2 and power <= 2:
                score -= 5.0

        # Pitch 1 é vantajoso no Arsenal (ataque chave para o turno seguinte)
        if pitch == 1:
            score += 5.0
        elif pitch == 3:
            # Pitch 3 no Arsenal é ruim (Arsenal não dá pitch e dano de azul é baixo)
            score -= 8.0

        if card_info.get("has_go_again", False):
            score += 2.0
        if card_info.get("cost", 0) == 0:
            score += 1.5

        # Instants com utilidade
        if card_type == "I" or any(k in c_name for k in ["sigil", "oasis", "whisper"]):
            score += 4.0

        return score


# ══════════════════════════════════════════════════════════════════
# 1. GUARDIAN STRATEGY (Bravo, Oldhim, Valda, Betsy, Victor, Brevant)
# ══════════════════════════════════════════════════════════════════

class GuardianStrategy(HeroStrategy):
    is_heavy_hero: bool = True

    def has_heavy_attack(self, card_info: dict) -> bool:
        c_name = card_info.get("name", "").lower()
        pitch = card_info.get("pitch", 1)
        power = card_info.get("power", 0)
        return (pitch == 1 and power >= 6) or any(w in c_name for w in [
            "crush", "wager", "overpower", "bet_big", "spinal", "crippling", "buckling",
            "macho", "pulverize", "star_struck", "anothos", "thunderquake", "chokeslam",
            "cartilage", "oaken", "boulder", "mangle", "felling", "plow_under",
            "command_and_conquer", "sledge", "titans_fist"
        ])

    @lru_cache(maxsize=1024)
    def evaluate_attack_card(self, card_name: str, power: int, cost: int, has_go_again: bool, pitch: int) -> float:
        score = float(power)
        c_low = card_name.lower()
        if any(w in c_low for w in [
            "crush", "wager", "overpower", "bet_big", "spinal", "crippling", "buckling",
            "macho", "pulverize", "star_struck", "anothos", "thunderquake", "chokeslam",
            "cartilage", "oaken", "boulder", "mangle", "felling", "plow_under",
            "command_and_conquer", "sledge", "titans_fist"
        ]):
            score += 6.0
        if pitch == 1 and power >= 6:
            score += 4.0
        return score

    @lru_cache(maxsize=1024)
    def evaluate_pitch_card(self, card_name: str, pitch: int, cost: int, power: int, has_go_again: bool) -> float:
        score = float(pitch) * 5.0
        if pitch == 3:
            score += 6.0
        elif pitch == 1:
            score -= 8.0  # Nunca pitcha ataques vermelhos pesados
        return score

    @lru_cache(maxsize=1024)
    def evaluate_block_card(self, card_name: str, block_val: int, pitch: int, power: int, has_go_again: bool) -> float:
        if block_val <= 0:
            return -999.0
        c_low = card_name.lower()
        if pitch == 1 and (power >= 6 or any(w in c_low for w in ["oaken", "boulder", "mangle", "felling", "crush", "command_and_conquer"])):
            return -25.0
        return float(block_val) * 2.0 - (power * 0.5)

    def evaluate_weapon_attack(self, card_name: str, floating_res: int, total_res: int, has_hand_attacks: bool) -> float:
        score = 4.5 + (2.0 if floating_res >= 1 else 0.0)
        if not has_hand_attacks:
            score += 4.5  # Martelo pesado para aplicar pressão quando sem ataque na mão
        return score

    def evaluate_arsenal_card(self, card_info: dict, db_entry: dict = None) -> float:
        score = super().evaluate_arsenal_card(card_info, db_entry)
        if score <= -1000:
            return score
        c_name = card_info.get("name", "").lower()
        pitch = card_info.get("pitch", 1)
        power = card_info.get("power", 0)
        # Ataques vermelhos pesados de Guardião (power >= 6) superam a penalidade de bloco porque são o Pivot
        if pitch == 1 and (power >= 6 or any(w in c_name for w in ["oaken", "boulder", "mangle", "felling", "crush", "command_and_conquer"])):
            score += 12.0
        # Reações de defesa e Auras defensivas (Channel Lake Frigid, Blizzard, Staunch Response)
        if any(k in c_name for k in ["staunch", "channel_lake", "channel_ice", "blizzard", "sink_below"]):
            score += 9.0
        return score


# ══════════════════════════════════════════════════════════════════
# 2. JARL STRATEGY (Guardião Elemental Terra e Gelo)
# ══════════════════════════════════════════════════════════════════

class JarlStrategy(GuardianStrategy):
    @lru_cache(maxsize=1024)
    def evaluate_attack_card(self, card_name: str, power: int, cost: int, has_go_again: bool, pitch: int) -> float:
        score = super().evaluate_attack_card(card_name, power, cost, has_go_again, pitch)
        c_low = card_name.lower()
        if "oaken_old" in c_low:
            score += 7.0
        elif "boulder_drop" in c_low or "felling_of_the_crown" in c_low:
            score += 5.0
        if any(k in c_low for k in ["ice", "blizzard", "frigid", "frost", "glaze"]):
            score += 3.0  # Cartas de Gelo criam Frostbite pelo gatilho do Jarl
        return score


# ══════════════════════════════════════════════════════════════════
# 3. BRUTE STRATEGY (Rhinar, Kayo, Levia, Baalghor)
# ══════════════════════════════════════════════════════════════════

class BruteStrategy(HeroStrategy):
    is_heavy_hero: bool = True

    def has_heavy_attack(self, card_info: dict) -> bool:
        return int(card_info.get("power", 0)) >= 6

    @lru_cache(maxsize=1024)
    def evaluate_attack_card(self, card_name: str, power: int, cost: int, has_go_again: bool, pitch: int) -> float:
        score = float(power)
        c_low = card_name.lower()
        # Ataques de poder 6+ acionam Intimidate, Beat Chest e habilidades de Bruto
        if power >= 6:
            score += 6.0
        if any(w in c_low for w in ["intimidate", "bloodrush", "beat_chest", "pummel", "swing_big", "pack_hunt", "scabskin", "wreck_havoc"]):
            score += 5.0
        if has_go_again:
            score += 4.0
        score -= cost * 0.4
        return score

    @lru_cache(maxsize=1024)
    def evaluate_pitch_card(self, card_name: str, pitch: int, cost: int, power: int, has_go_again: bool) -> float:
        score = float(pitch) * 4.5
        # Preserva cartas de poder 6+ na mão para descarte de habilidades (Kayo/Rhinar/Levia)
        if power >= 6:
            score -= 3.0
        if pitch == 3:
            score += 4.0
        return score

    @lru_cache(maxsize=1024)
    def evaluate_block_card(self, card_name: str, block_val: int, pitch: int, power: int, has_go_again: bool) -> float:
        if block_val <= 0:
            return -999.0
        # Preserva cartas de ataque 6+ para bater forte no pivot
        if pitch == 1 and power >= 6:
            return -20.0
        return float(block_val) * 2.0 - (power * 0.5)

    def evaluate_weapon_attack(self, card_name: str, floating_res: int, total_res: int, has_hand_attacks: bool) -> float:
        score = 4.0 + (2.0 if floating_res >= 1 else 0.0)
        if not has_hand_attacks:
            score += 3.5
        return score


# ══════════════════════════════════════════════════════════════════
# 4. WARRIOR STRATEGY (Dorinthea, Kassai, Boltyn, Olympia, Fang, Hala)
# ══════════════════════════════════════════════════════════════════

class WarriorStrategy(HeroStrategy):
    is_heavy_hero: bool = False

    @lru_cache(maxsize=1024)
    def evaluate_attack_card(self, card_name: str, power: int, cost: int, has_go_again: bool, pitch: int) -> float:
        score = float(power)
        c_low = card_name.lower()
        if any(w in c_low for w in ["reprise", "glint", "ironsong", "singing_steel", "spoils_of_war", "out_for_blood", "hit_and_run", "stroke"]):
            score += 5.0
        if has_go_again:
            score += 4.0
        return score

    def evaluate_weapon_attack(self, card_name: str, floating_res: int, total_res: int, has_hand_attacks: bool) -> float:
        # Guerreiro: O ataque com a arma (Dawnblade, Sabers, Raydn, Hatchets) é o centro absoluto da estratégia!
        # Atacar com a arma força defesas da mão e ativa o efeito Reprise
        score = 10.0 + (2.0 if floating_res >= 1 else 0.0)
        return score

    @lru_cache(maxsize=1024)
    def evaluate_block_card(self, card_name: str, block_val: int, pitch: int, power: int, has_go_again: bool) -> float:
        if block_val <= 0:
            return -999.0
        c_low = card_name.lower()
        # Guerreiro preserva Reações de Ataque na mão para forçar dano na etapa de reações
        if any(w in c_low for w in ["ironsong", "glint", "steelblade", "stroke", "blade_runner"]):
            return -15.0
        return float(block_val) * 2.0 - power

    def evaluate_arsenal_card(self, card_info: dict, db_entry: dict = None) -> float:
        c_name = card_info.get("name", "").lower()
        pitch = card_info.get("pitch", 1)
        power = card_info.get("power", 0)
        block_val = card_info.get("block", 0)
        subtype = (db_entry.get("subtype", "") if db_entry else "").lower()
        card_type = (db_entry.get("type", "") if db_entry else "").upper()
        card_text = (db_entry.get("text", "") if db_entry else "").lower()

        # 1. Poda estrita universal: Recursos e Gemas proibidos no Arsenal
        if is_resource_or_gem_card(c_name, card_info, db_entry):
            return -9999.0

        # 2. Exceções com Vantagem: Ambush e Down and Dirty
        is_down_and_dirty = "down_and_dirty" in c_name or "down and dirty" in c_name
        has_ambush = (
            "ambush" in subtype
            or "ambush" in card_text
            or "defend with this from your arsenal" in card_text
            or "ambush" in c_name
            or is_down_and_dirty
        )
        if is_down_and_dirty:
            return 16.0
        if has_ambush:
            return 13.0

        # 3. Flechas (Arrows): Prioridade #1 absoluta do Ranger
        is_arrow = "arrow" in subtype or any(k in c_name for k in ["arrow", "harpoon", "bolt", "trophy_shot", "endless_arrow"])
        if is_arrow:
            score = 20.0
            if pitch == 1:
                score += 5.0
            elif pitch == 2:
                score += 2.0
            score += float(power) * 0.5
            return score

        # 4. Buffs de ataque / Ações Não-Ataque de Ranger
        if any(k in c_name for k in ["three_of_a_kind", "rain_razors", "take_aim", "seek_horizon", "premeditation", "codex"]):
            score = 12.0
            if pitch == 1:
                score += 2.0
            return score

        # 5. Reações de Defesa e Armadilhas (Traps)
        is_dr = "trap" in subtype or card_type == "DR" or any(k in c_name for k in ["trap", "sink_below", "fate_foreseen", "shelter", "take_cover"])
        if is_dr:
            return 9.0

        # 6. Cartas comuns de ação com valor de bloqueio que NÃO são flechas nem DR:
        score = float(power)
        if block_val >= 3:
            score -= 8.0
            if power <= 3:
                score -= 6.0
        if pitch == 3:
            score -= 14.0

        return score


# ══════════════════════════════════════════════════════════════════
# 5. NINJA STRATEGY (Katsu, Ira, Fai, Benji, Zen, Cindra)
# ══════════════════════════════════════════════════════════════════

class NinjaStrategy(HeroStrategy):
    is_heavy_hero: bool = False

    @lru_cache(maxsize=1024)
    def evaluate_attack_card(self, card_name: str, power: int, cost: int, has_go_again: bool, pitch: int) -> float:
        score = float(power)
        c_low = card_name.lower()
        if "surge" in c_low or "leg_tap" in c_low or "rising_knee" in c_low or "roaring_tiger" in c_low:
            score += 4.0
        if has_go_again:
            score += 5.0
        if cost == 0:
            score += 2.0
        return score

    def evaluate_weapon_attack(self, card_name: str, floating_res: int, total_res: int, has_hand_attacks: bool) -> float:
        # Harmonized Kodachi swings
        score = 4.0 + (2.0 if floating_res >= 1 else 0.0)
        return score


# ══════════════════════════════════════════════════════════════════
# 6. RANGER STRATEGY (Azalea, Lexi, Riptide, Marlynn / Marlinn)
# ══════════════════════════════════════════════════════════════════

class RangerStrategy(HeroStrategy):
    is_heavy_hero: bool = False

    @lru_cache(maxsize=1024)
    def evaluate_attack_card(self, card_name: str, power: int, cost: int, has_go_again: bool, pitch: int) -> float:
        score = float(power)
        c_low = card_name.lower()
        if any(k in c_low for k in ["arrow", "harpoon", "bolt", "trophy", "scoundrel", "rabble"]):
            score += 6.0
        if has_go_again:
            score += 4.0
        score -= cost * 0.5
        if pitch == 1:
            score += 3.0
        return score

    def evaluate_arsenal_card(self, card_info: dict, db_entry: dict = None) -> float:
        c_name = card_info.get("name", "").lower()
        pitch = card_info.get("pitch", 1)
        power = card_info.get("power", 0)
        block_val = card_info.get("block", 0)
        subtype = (card_info.get("subtype") or (db_entry.get("subtype", "") if db_entry else "")).lower()
        card_type = (card_info.get("type") or (db_entry.get("type", "") if db_entry else "")).upper()
        card_text = (card_info.get("text") or (db_entry.get("text", "") if db_entry else "")).lower()

        # 1. Poda estrita universal: Recursos e Gemas proibidos no Arsenal
        if is_resource_or_gem_card(c_name, card_info, db_entry):
            return -9999.0

        # 2. Exceções com Vantagem: Ambush e Down and Dirty
        is_down_and_dirty = "down_and_dirty" in c_name or "down and dirty" in c_name
        has_ambush = (
            c_name in KNOWN_AMBUSH_CARDS
            or any(k in c_name for k in ["stadium_security", "down_and_dirty", "no_hero_stands_alone", "overcrowded", "tiger_eye_reflex"])
            or "ambush" in subtype
            or "ambush" in card_text
            or "defend with this from your arsenal" in card_text
            or "ambush" in c_name
            or is_down_and_dirty
        )
        if is_down_and_dirty:
            return 16.0
        if has_ambush:
            return 13.0

        # 3. Flechas (Arrows): Prioridade #1 absoluta do Ranger
        is_arrow = "arrow" in subtype or any(k in c_name for k in ["arrow", "harpoon", "bolt", "trophy_shot", "endless_arrow"])
        if is_arrow:
            score = 20.0
            if pitch == 1:
                score += 5.0
            elif pitch == 2:
                score += 2.0
            score += float(power) * 0.5
            return score

        # 4. Buffs de ataque / Ações Não-Ataque de Ranger
        if any(k in c_name for k in ["three_of_a_kind", "rain_razors", "take_aim", "seek_horizon", "premeditation", "codex"]):
            score = 12.0
            if pitch == 1:
                score += 2.0
            return score

        # 5. Reações de Defesa e Armadilhas (Traps)
        is_dr = "trap" in subtype or card_type == "DR" or any(k in c_name for k in ["trap", "sink_below", "fate_foreseen", "shelter", "take_cover"])
        if is_dr:
            return 9.0

        # 6. Cartas comuns de ação com valor de bloqueio que NÃO são flechas nem DR:
        score = float(power)
        if block_val >= 3:
            score -= 8.0
            if power <= 3:
                score -= 6.0
        if pitch == 3:
            score -= 14.0

        return score


# ══════════════════════════════════════════════════════════════════
# 7. MECHANOLOGIST STRATEGY (Dash, Maxx, Teklovossen, Data Doll, Puffin)
# ══════════════════════════════════════════════════════════════════

class MechanologistStrategy(HeroStrategy):
    is_heavy_hero: bool = False

    @lru_cache(maxsize=1024)
    def evaluate_attack_card(self, card_name: str, power: int, cost: int, has_go_again: bool, pitch: int) -> float:
        score = super().evaluate_attack_card(card_name, power, cost, has_go_again, pitch)
        c_low = card_name.lower()
        if "zero_to_sixty" in c_low or "zipper" in c_low:
            score += 3.0
        elif "throttle" in c_low or "fast_and_furious" in c_low or "high_octane" in c_low:
            score += 2.5
        return score

    def should_boost(self, card_name: str, hand_size: int, deck_size: int) -> bool:
        return deck_size > 6

    def should_crank(self, item_name: str, has_actions_left: bool) -> bool:
        return True


# ══════════════════════════════════════════════════════════════════
# 8. RUNEBLADE STRATEGY (Viserai, Chane, Briar, Vynnset, Florian, Aurora)
# ══════════════════════════════════════════════════════════════════

class RunebladeStrategy(HeroStrategy):
    is_heavy_hero: bool = False

    @lru_cache(maxsize=1024)
    def evaluate_attack_card(self, card_name: str, power: int, cost: int, has_go_again: bool, pitch: int) -> float:
        score = float(power)
        c_low = card_name.lower()
        if any(w in c_low for w in ["runeblood", "arknight", "rift_bind", "mauvrion", "rosetta", "revel", "meat_grinder", "duskpath"]):
            score += 4.0
        if has_go_again:
            score += 4.0
        return score

    def evaluate_weapon_attack(self, card_name: str, floating_res: int, total_res: int, has_hand_attacks: bool) -> float:
        # Rosetta Thorn / Nebula Blade / Galaxxi Black (ataque misto físico + arcano)
        score = 6.0 + (2.0 if floating_res >= 1 else 0.0)
        return score


# ══════════════════════════════════════════════════════════════════
# 9. WIZARD STRATEGY (Kano, Iyslander, Verdance, Oscilio, Blaze, Emperor)
# ══════════════════════════════════════════════════════════════════

class WizardStrategy(HeroStrategy):
    is_heavy_hero: bool = False

    @lru_cache(maxsize=1024)
    def evaluate_attack_card(self, card_name: str, power: int, cost: int, has_go_again: bool, pitch: int) -> float:
        score = float(power)
        c_low = card_name.lower()
        if any(w in c_low for w in ["sonic_boom", "zap", "aether", "spindle", "chain_lightning", "emergent"]):
            score += 5.0
        return score

    @lru_cache(maxsize=1024)
    def evaluate_pitch_card(self, card_name: str, pitch: int, cost: int, power: int, has_go_again: bool) -> float:
        score = float(pitch) * 5.0
        # Mago exige pitch azul (3 recursos) para ativar Crucible e queimar dano instantâneo
        if pitch == 3:
            score += 8.0
        return score

    def evaluate_weapon_attack(self, card_name: str, floating_res: int, total_res: int, has_hand_attacks: bool) -> float:
        # Ativações de Crucible of Aetherweave / Volzar
        score = 5.0 + (2.0 if floating_res >= 1 else 0.0)
        return score


# ══════════════════════════════════════════════════════════════════
# 10. ILLUSIONIST STRATEGY (Prism, Dromai, Enigma, Pleiades, Zyggy)
# ══════════════════════════════════════════════════════════════════

class IllusionistStrategy(HeroStrategy):
    is_heavy_hero: bool = False

    @lru_cache(maxsize=1024)
    def evaluate_attack_card(self, card_name: str, power: int, cost: int, has_go_again: bool, pitch: int) -> float:
        score = float(power)
        c_low = card_name.lower()
        if any(w in c_low for w in ["herald", "phantasm", "miragai", "kyloria", "cromai", "spectral", "ward"]):
            score += 4.5
        if has_go_again:
            score += 4.0
        return score

    def evaluate_weapon_attack(self, card_name: str, floating_res: int, total_res: int, has_hand_attacks: bool) -> float:
        score = 4.0 + (2.0 if floating_res >= 1 else 0.0)
        return score


# ══════════════════════════════════════════════════════════════════
# 11. ASSASSIN STRATEGY (Arakni, Uzuri, Nuu, Dr. Mortimer)
# ══════════════════════════════════════════════════════════════════

class AssassinStrategy(HeroStrategy):
    is_heavy_hero: bool = False

    @lru_cache(maxsize=1024)
    def evaluate_attack_card(self, card_name: str, power: int, cost: int, has_go_again: bool, pitch: int) -> float:
        score = float(power)
        c_low = card_name.lower()
        # Foco em cartas de Stealth, Contratos e gatilhos de banimento
        if any(w in c_low for w in ["stealth", "contract", "surgical", "leave_no_witnesses", "erase_face", "sneak", "infiltrate"]):
            score += 5.0
        if has_go_again:
            score += 4.0
        return score

    def evaluate_weapon_attack(self, card_name: str, floating_res: int, total_res: int, has_hand_attacks: bool) -> float:
        # Spider's Bite / Scale Peeler (Dagger com Piercing 1)
        score = 5.0 + (2.0 if floating_res >= 1 else 0.0)
        return score


# ══════════════════════════════════════════════════════════════════
# 12. MERCHANT / BARD / MISC STRATEGY (Genis, Kavdaen, Melody, etc.)
# ══════════════════════════════════════════════════════════════════

class MerchantStrategy(HeroStrategy):
    is_heavy_hero: bool = False


# ══════════════════════════════════════════════════════════════════
# REGISTRO CANÔNICO EXAUSTIVO DOS 139 HERÓIS DE FLESH AND BLOOD
# ══════════════════════════════════════════════════════════════════

HERO_CLASS_REGISTRY: Dict[str, type] = {
    # ── GUARDIAN ────────────────────────────────────────────────
    "bravo_showstopper": GuardianStrategy,
    "bravo": GuardianStrategy,
    "bravo_star_of_the_show": GuardianStrategy,
    "bravo_flattering_showman": GuardianStrategy,
    "oldhim_grandfather_of_eternity": GuardianStrategy,
    "oldhim": GuardianStrategy,
    "valda_brightaxe": GuardianStrategy,
    "valda_seismic_impact": GuardianStrategy,
    "valda": GuardianStrategy,
    "betsy_skin_in_the_game": GuardianStrategy,
    "betsy": GuardianStrategy,
    "victor_goldmane_high_and_mighty": GuardianStrategy,
    "victor_goldmane": GuardianStrategy,
    "victor": GuardianStrategy,
    "yoji_royal_protector": GuardianStrategy,
    "yoji": GuardianStrategy,
    "brevant_civic_protector": GuardianStrategy,
    "brevant": GuardianStrategy,
    "tuffnut_bumbling_hulkster": GuardianStrategy,
    "tuffnut": GuardianStrategy,
    "lyath_goldmane_vile_savant": GuardianStrategy,
    "lyath_goldmane": GuardianStrategy,
    "lyath": GuardianStrategy,
    "terra": GuardianStrategy,
    "guardian": GuardianStrategy,

    # ── JARL (Elemental Guardian Terra/Gelo) ─────────────────────
    "jarl_vetreidi": JarlStrategy,
    "jarl": JarlStrategy,

    # ── BRUTE ───────────────────────────────────────────────────
    "rhinar_reckless_rampage": BruteStrategy,
    "rhinar": BruteStrategy,
    "kayo_berserker_runt": BruteStrategy,
    "kayo_armed_and_dangerous": BruteStrategy,
    "kayo_underhanded_cheat": BruteStrategy,
    "kayo_strong-arm": BruteStrategy,
    "kayo": BruteStrategy,
    "levia_shadowborn_abomination": BruteStrategy,
    "levia": BruteStrategy,
    "baalghor_omen_of_the_end": BruteStrategy,
    "baalghor": BruteStrategy,
    "brute": BruteStrategy,

    # ── RANGER ──────────────────────────────────────────────────
    "azalea_ace_in_the_hole": RangerStrategy,
    "azalea": RangerStrategy,
    "lexi_livewire": RangerStrategy,
    "lexi": RangerStrategy,
    "riptide_lurker_of_the_deep": RangerStrategy,
    "riptide": RangerStrategy,
    "marlynn_treasure_hunter": RangerStrategy,
    "marlynn": RangerStrategy,
    "marlinn": RangerStrategy,
    "ranger": RangerStrategy,

    # ── NINJA ───────────────────────────────────────────────────
    "katsu_the_wanderer": NinjaStrategy,
    "katsu": NinjaStrategy,
    "ira_crimson_haze": NinjaStrategy,
    "ira_scarlet_revenger": NinjaStrategy,
    "ira": NinjaStrategy,
    "benji_the_piercing_wind": NinjaStrategy,
    "benji": NinjaStrategy,
    "fai_rising_rebellion": NinjaStrategy,
    "fai": NinjaStrategy,
    "zen_tamer_of_purpose": NinjaStrategy,
    "zen": NinjaStrategy,
    "cindra_dracai_of_retribution": NinjaStrategy,
    "cindra": NinjaStrategy,
    "ninja": NinjaStrategy,

    # ── WARRIOR ─────────────────────────────────────────────────
    "dorinthea_ironsong": WarriorStrategy,
    "dorinthea_quicksilver_prodigy": WarriorStrategy,
    "dorinthea": WarriorStrategy,
    "kassai_cintari_sellsword": WarriorStrategy,
    "kassai_of_the_golden_sand": WarriorStrategy,
    "kassai": WarriorStrategy,
    "ser_boltyn_breaker_of_dawn": WarriorStrategy,
    "boltyn": WarriorStrategy,
    "olympia_prized_fighter": WarriorStrategy,
    "olympia": WarriorStrategy,
    "fang_dracai_of_blades": WarriorStrategy,
    "fang": WarriorStrategy,
    "hala_bladesaint_of_the_vow": WarriorStrategy,
    "hala": WarriorStrategy,
    "killjoy_the_crooked_blade": WarriorStrategy,
    "killjoy": WarriorStrategy,
    "warrior": WarriorStrategy,

    # ── MECHANOLOGIST ───────────────────────────────────────────
    "dash_inventor_extraordinaire": MechanologistStrategy,
    "dash_io": MechanologistStrategy,
    "dash_database": MechanologistStrategy,
    "dash": MechanologistStrategy,
    "data_doll_mkii": MechanologistStrategy,
    "data_doll": MechanologistStrategy,
    "professor_teklovossen": MechanologistStrategy,
    "teklovossen_esteemed_magnate": MechanologistStrategy,
    "teklovossen": MechanologistStrategy,
    "maxx_the_hype_nitro": MechanologistStrategy,
    "maxx_nitro": MechanologistStrategy,
    "maxx": MechanologistStrategy,
    "puffin_hightail": MechanologistStrategy,
    "puffin": MechanologistStrategy,
    "mechanologist": MechanologistStrategy,

    # ── RUNEBLADE ───────────────────────────────────────────────
    "viserai_rune_blood": RunebladeStrategy,
    "viserai_the_forsaken": RunebladeStrategy,
    "viserai_between_worlds": RunebladeStrategy,
    "viserai": RunebladeStrategy,
    "chane_bound_by_shadow": RunebladeStrategy,
    "chane": RunebladeStrategy,
    "briar_warden_of_thorns": RunebladeStrategy,
    "briar": RunebladeStrategy,
    "vynnset_iron_maiden": RunebladeStrategy,
    "vynnset": RunebladeStrategy,
    "florian_rotwood_harbinger": RunebladeStrategy,
    "florian": RunebladeStrategy,
    "aurora_shooting_star": RunebladeStrategy,
    "aurora_legacy_of_tempest": RunebladeStrategy,
    "aurora_emissary_of_lightning": RunebladeStrategy,
    "aurora": RunebladeStrategy,
    "runeblade": RunebladeStrategy,

    # ── WIZARD ──────────────────────────────────────────────────
    "kano_dracai_of_aether": WizardStrategy,
    "kano": WizardStrategy,
    "iyslander_stormbind": WizardStrategy,
    "iyslander": WizardStrategy,
    "blaze_firemind": WizardStrategy,
    "blaze": WizardStrategy,
    "verdance_thorn_of_the_rose": WizardStrategy,
    "verdance": WizardStrategy,
    "oscilio_constella_intelligence": WizardStrategy,
    "oscilio_forked_continuum": WizardStrategy,
    "oscilio_scion_of_the_third_age": WizardStrategy,
    "oscilio": WizardStrategy,
    "emperor_dracai_of_aesir": WizardStrategy,
    "emperor": WizardStrategy,
    "wizard": WizardStrategy,

    # ── ILLUSIONIST ─────────────────────────────────────────────
    "prism_sculptor_of_arc_light": IllusionistStrategy,
    "prism_awakener_of_sol": IllusionistStrategy,
    "prism_advent_of_thrones": IllusionistStrategy,
    "prism": IllusionistStrategy,
    "dromai_ash_artist": IllusionistStrategy,
    "dromai": IllusionistStrategy,
    "enigma_ledger_of_ancestry": IllusionistStrategy,
    "enigma_new_moon": IllusionistStrategy,
    "enigma": IllusionistStrategy,
    "pleiades_superstar": IllusionistStrategy,
    "pleiades": IllusionistStrategy,
    "zyggy_starlight": IllusionistStrategy,
    "zyggy": IllusionistStrategy,
    "illusionist": IllusionistStrategy,

    # ── ASSASSIN ────────────────────────────────────────────────
    "arakni_huntsman": AssassinStrategy,
    "arakni_solitary_confinement": AssassinStrategy,
    "arakni_marionette": AssassinStrategy,
    "arakni_web_of_deceit": AssassinStrategy,
    "arakni_5lp3d_7hru_7h3_cr4x": AssassinStrategy,
    "arakni": AssassinStrategy,
    "uzuri_switchblade": AssassinStrategy,
    "uzuri": AssassinStrategy,
    "nuu_alluring_desire": AssassinStrategy,
    "nuu": AssassinStrategy,
    "dr_mortimer_blight_of_the_pits": AssassinStrategy,
    "dr_mortimer": AssassinStrategy,
    "assassin": AssassinStrategy,

    # ── MERCHANT / BARD / MISC ──────────────────────────────────
    "kavdaen_trader_of_skins": MerchantStrategy,
    "kavdaen": MerchantStrategy,
    "genis_wotchuneed": MerchantStrategy,
    "genis": MerchantStrategy,
    "melody_sing-along": MerchantStrategy,
    "melody": MerchantStrategy,
    "shiyana_diamond_gemini": MerchantStrategy,
    "shiyana": MerchantStrategy,
    "gravy_bones_shipwrecked_looter": MerchantStrategy,
    "gravy_bones": MerchantStrategy,
    "scurv_stowaway": MerchantStrategy,
    "scurv": MerchantStrategy,
    "malice_domina_of_the_dead": MerchantStrategy,
    "malice": MerchantStrategy,
    "zane_broadly_beloved": MerchantStrategy,
    "zane": MerchantStrategy,
}


@lru_cache(maxsize=256)
def get_hero_strategy(hero_name: str) -> HeroStrategy:
    """
    Fábrica canônica de estratégias de herói de Flesh and Blood.
    1. Resolução direta via HERO_CLASS_REGISTRY.
    2. Resolução por prefixo/raiz (ex: 'dorinthea' em 'dorinthea_custom').
    3. Fallback dinâmico via consulta a 'data/fab_cards_db.json' (classes FaB oficiais).
    """
    h = str(hero_name).lower().strip()

    # 1. Correspondência direta no registro canônico
    if h in HERO_CLASS_REGISTRY:
        return HERO_CLASS_REGISTRY[h](h)

    # 2. Correspondência por raiz do nome (split por '_')
    root = h.split('_')[0]
    if root in HERO_CLASS_REGISTRY:
        return HERO_CLASS_REGISTRY[root](h)

    # 3. Fallback dinâmico via Card Database
    cards_db = _get_cards_db()
    for candidate in (h, f"{h}_young", f"{h}_adult", root):
        cdata = cards_db.get(candidate, {})
        c_class = str(cdata.get("class", "")).upper()
        subtype = str(cdata.get("subtype", "")).upper()

        if "JARL" in candidate.upper():
            return JarlStrategy(h)
        elif "GUARDIAN" in c_class or "GUARDIAN" in subtype:
            return GuardianStrategy(h)
        elif "BRUTE" in c_class or "BRUTE" in subtype:
            return BruteStrategy(h)
        elif "RANGER" in c_class or "RANGER" in subtype:
            return RangerStrategy(h)
        elif "NINJA" in c_class or "NINJA" in subtype:
            return NinjaStrategy(h)
        elif "WARRIOR" in c_class or "WARRIOR" in subtype:
            return WarriorStrategy(h)
        elif "MECHANOLOGIST" in c_class or "MECHANOLOGIST" in subtype:
            return MechanologistStrategy(h)
        elif "RUNEBLADE" in c_class or "RUNEBLADE" in subtype:
            return RunebladeStrategy(h)
        elif "WIZARD" in c_class or "WIZARD" in subtype:
            return WizardStrategy(h)
        elif "ILLUSIONIST" in c_class or "ILLUSIONIST" in subtype:
            return IllusionistStrategy(h)
        elif "ASSASSIN" in c_class or "ASSASSIN" in subtype:
            return AssassinStrategy(h)
        elif "MERCHANT" in c_class or "BARD" in c_class or "PIRATE" in c_class:
            return MerchantStrategy(h)

    return HeroStrategy(h)
