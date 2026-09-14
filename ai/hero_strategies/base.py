"""
ai/hero_strategies/base.py
==========================
Definição base de TurnPlan, utilitários globais de cartas e HeroStrategy.
"""

import os
import json
import itertools
from functools import lru_cache
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Set, List, Tuple

_FAB_CARDS_DB = None

def _get_cards_db() -> dict:
    global _FAB_CARDS_DB
    if _FAB_CARDS_DB is None:
        db_paths = [
            "data/fab_cards_db.json",
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "fab_cards_db.json"),
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


KNOWN_AMBUSH_CARDS: Set[str] = {
    "down_and_dirty_red", "down_and_dirty",
    "stadium_security_red", "stadium_security_yellow", "stadium_security_blue",
    "no_hero_stands_alone_yellow", "overcrowded_blue",
    "tiger_eye_reflex_yellow", "tiger_eye_reflex_blue",
}

DANGEROUS_ON_HITS = [
    "command_and_conquer", "cn_c", "snatch", "red_in_the_ledger",
    "crippling_crush", "spinal_crush", "star_struck", "leave_no_witnesses",
    "bloodrush_bellow", "warmonger", "inertia", "blood_drop",
    "shake_down", "mask_of_momentum", "codex_of_frailty"
]


@dataclass
class TurnPlan:
    """
    Plano tático de ação para o turno atual.
    Coordena decisões ofensivas e defensivas entre a etapa de bloqueio e ataque.
    """
    plan_type: str = "DEFAULT"
    reserved_card_names: Set[str] = field(default_factory=set)
    can_absorb_damage: bool = False
    max_block_cards: int = 4
    priority_action_types: List[str] = field(default_factory=list)
    offensive_potential: float = 0.0
    reason: str = ""


class HeroStrategy:
    """Estratégia base genérica para heróis de Flesh and Blood."""
    is_heavy_hero: bool = False

    def __init__(self, hero_name: str = "generic"):
        self.hero_name = str(hero_name).lower().strip()

    def get_dynamic_multiplier(self, key: str, default: float = 1.0) -> float:
        """Obtém o multiplicador tático dinamicamente calibrado para o herói atual."""
        try:
            from ai.dynamic_rule_tuner import get_multipliers_for_hero
            mults = get_multipliers_for_hero(self.hero_name)
            return float(mults.get(key, default))
        except Exception:
            return default

    def has_heavy_attack(self, card_info: dict) -> bool:
        """Determina se uma carta é um ataque pesado que justifica linha de Pivot."""
        return False

    def evaluate_attack_card(self, card_name: str, power: int, cost: int, has_go_again: bool, pitch: int) -> float:
        """Calcula score de prioridade de ataque na cadeia de combate calibrado por attack_weight."""
        atk_mult = self.get_dynamic_multiplier("attack_weight", 1.0)
        score = float(power) * atk_mult
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
        if pitch <= 0:
            return -9999.0
        score = float(pitch) * 4.0
        if power >= 4:
            score -= 2.0
        if has_go_again:
            score -= 2.0
        if pitch == 1:
            score -= 3.0
        return score

    def evaluate_hero_ability(self, state: dict, hero_info: dict) -> float:
        """Pontuação tática para ativar a habilidade do Herói (Character Ability)."""
        return 0.0

    def evaluate_card_priority(self, card_name: str, cost: int, pitch: int, power: int, has_go_again: bool) -> float:
        return self.evaluate_attack_card(card_name, power, cost, has_go_again, pitch)

    def should_boost(self, card_name: str, hand_size: int, deck_size: int) -> bool:
        return deck_size > 5

    def should_crank(self, item_name: str, has_actions_left: bool) -> bool:
        return True

    def evaluate_block_card(self, card_name: str, block_val: int, pitch: int, power: int, has_go_again: bool, **kwargs) -> float:
        """Calcula score defensivo calibrado por block_weight."""
        if block_val <= 0:
            return -999.0
        blk_mult = self.get_dynamic_multiplier("block_weight", 1.0)
        offensive_value = power + (3.0 if has_go_again else 0.0)
        return (float(block_val) * 2.0 * blk_mult) - offensive_value

    def evaluate_weapon_attack(self, card_name: str, floating_res: int, total_res: int, has_hand_attacks: bool, **kwargs) -> float:
        """Pontuação tática para atacar com a arma equipada."""
        score = 3.0 + (2.0 if floating_res >= 1 else 0.0)
        if not has_hand_attacks:
            score += 2.5
        return score

    def evaluate_weapon_ability(
        self,
        weapon_name: str,
        weapon_cost: int,
        state: dict,
        total_res: int,
        turn_plan: Optional[TurnPlan] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Pontuação e validação de ativação para habilidades de armas (ex: Hammerhead Harpoon Cannon).
        Retorna:
          - Dict com dados do candidato (score, cost, power, etc.) se for uma habilidade de arma válida.
          - {} (dicionário vazio) se a habilidade existe mas foi podada/inválida no estado atual.
          - None se a arma não possui habilidade especial e deve ser tratada como ataque convencional.
        """
        return None

    def evaluate_hero_ability(self, state: dict, hero_info: dict) -> float:
        """Pontuação tática para ativar a habilidade do Herói."""
        return 0.0

    def evaluate_equipment_ability(self, state_or_name, eq_info_or_floating: Any = None, hand_attacks: list = None, **kwargs) -> float:
        """
        Pontuação tática para ativar habilidades de equipamento (Head, Chest, Arms, Legs, Off-Hand).
        Abordagem 100% orientada a dados e semântica de regras, sem hardcoding de nomes de cartas,
        calibrada dinamicamente pelo motor de aprendizado persistente EquipmentLearningEngine.
        Suporta chamadas polimórficas (state, eq_info) ou legadas (eq_name, floating_res, total_res).
        """
        if isinstance(state_or_name, dict):
            state = state_or_name
            eq_info = eq_info_or_floating if isinstance(eq_info_or_floating, dict) else kwargs.get("eq_info", {})
            eq_name = str(eq_info.get("cardNumber") or eq_info.get("name", "")).lower().strip()
        else:
            eq_name = str(state_or_name or "").lower().strip()
            state = kwargs.get("state", {})
            eq_info = kwargs.get("eq_info", {"cardNumber": eq_name})

        if not eq_name:
            return 0.0

        from ai.equipment_learning import load_equipment_metadata, get_equipment_learning_engine
        eq_meta = load_equipment_metadata().get(eq_name, {})
        cards_db = _get_cards_db()
        hand = state.get("playerHand", [])
        arsenal = state.get("playerArsenal", [])

        # Se for equipamento puramente defensivo ou de prevenção (ex: ward, barrier, prevent):
        # Na fase principal, sem dano ativo na cadeia, nunca deve pontuar para ativação no vazio!
        is_defensive_instant = bool(
            "ward" in eq_name
            or "barrier" in eq_name
            or "prevent" in eq_name
            or eq_meta.get("is_defense_reaction")
        )
        if is_defensive_instant:
            active_chain = state.get("activeChainLink") or {}
            opp_pow = int(active_chain.get("totalPower", state.get("combatChainPower", 0)))
            if opp_pow <= 0 and int(state.get("arcaneDamage", 0)) <= 0:
                return 0.0

        # 1. Validação de requisitos de contadores (ex: contadores mínimos exigidos)
        req_counters = int(eq_meta.get("req_counters", 0))
        if req_counters > 0:
            current_counters = int(eq_info.get("counters", 0) or 0)
            if current_counters < req_counters:
                return 0.0

        # 2. Avaliação semântica da habilidade
        power_buff = int(eq_meta.get("power_buff", 0))
        min_atk_cost = int(eq_meta.get("min_attack_cost", 0))
        cost_discount = int(eq_meta.get("cost_discount", 0))
        grants_res = int(eq_meta.get("grants_resource", 0))
        creates_token = str(eq_meta.get("creates_token", ""))
        grants_ga = bool(eq_meta.get("grants_go_again", False))
        has_ga = bool(eq_meta.get("has_go_again", False))
        ab_cost = int(eq_meta.get("ability_cost", 0))

        base_score = 0.0

        # Caso A: Buff de poder para ataques
        if power_buff > 0:
            if hand_attacks:
                heavy = [a for a in hand_attacks if int(a.get("cost", 0)) >= min_atk_cost]
                if heavy:
                    base_score = max(float(a.get("score", 0.0)) for a in heavy) + float(power_buff) * 3.0
                else:
                    return 0.0
            else:
                heavy_attacks = [
                    c for c in list(hand) + list(arsenal)
                    if int(c.get("cost", cards_db.get(str(c.get("cardNumber", c.get("name", ""))).lower(), {}).get("cost", 0))) >= min_atk_cost
                ]
                if not heavy_attacks:
                    return 0.0
                base_score = 20.0 + float(power_buff) * 2.5

        # Caso B: Desconto de custo de recurso
        elif cost_discount > 0:
            target_min_cost = 2 if cost_discount >= 2 else 1
            if hand_attacks:
                cost_targets = [a for a in hand_attacks if int(a.get("cost", 0)) >= target_min_cost]
                if cost_targets:
                    base_score = max(float(a.get("score", 0.0)) for a in cost_targets) + float(cost_discount) * 2.5
                else:
                    return 0.0
            else:
                cost_targets = [
                    c for c in list(hand) + list(arsenal)
                    if int(c.get("cost", cards_db.get(str(c.get("cardNumber", c.get("name", ""))).lower(), {}).get("cost", 0))) >= target_min_cost
                ]
                if not cost_targets:
                    return 0.0
                base_score = 20.0 + float(cost_discount) * 2.0

        # Caso C: Geração de recursos
        elif grants_res > 0:
            base_score = 12.0 + float(grants_res) * 2.0

        # Caso D: Criação de Tokens (ex: Seismic Surge)
        elif creates_token:
            base_score = 14.0

        # Caso E: Concessão de Go Again
        elif grants_ga:
            base_score = 16.0

        # Caso F: Outras habilidades ativas
        else:
            ab_type = str(eq_meta.get("ability_type", "")).upper()
            if ab_type in ("A", "AR", "I", "AA"):
                base_score = 10.0
            else:
                base_score = 0.0

        if base_score <= 0.0:
            return 0.0

        if has_ga:
            base_score += 4.0
        if ab_cost > 0:
            base_score -= float(ab_cost) * 1.5

        # 3. Calibração empírica aprendida por herói / arquétipo
        learned_mult = get_equipment_learning_engine().get_equipment_multiplier(self.hero_name, eq_name)
        return max(0.0, base_score * learned_mult)

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
        block_val = card_info.get("block", card_info.get("defense", 0))
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
            score += 12.0
            if pitch == 1:
                score += 3.0
            return score
        elif has_ambush:
            score += 9.0
            if block_val >= 3:
                score += 3.0
            return score
        elif is_defense_reaction:
            score += 7.0
            if card_info.get("cost", 0) <= 1:
                score += 2.0
        else:
            if block_val >= 3:
                score -= 8.0
                if power <= 3:
                    score -= 6.0
            elif block_val == 2 and power <= 2:
                score -= 5.0

        if pitch == 1:
            score += 5.0
        elif pitch == 3:
            score -= 8.0

        if card_info.get("has_go_again", False):
            score += 2.0
        if card_info.get("cost", 0) == 0:
            score += 1.5

        if card_type == "I" or any(k in c_name for k in ["sigil", "oasis", "whisper"]):
            score += 4.0

        if score > 0:
            score *= self.get_dynamic_multiplier("arsenal_bonus", 1.0)

        return score

    def solve_knapsack_turn(
        self,
        hand: list,
        floating_res: int = 0,
        base_ap: int = 1,
        arsenal: Optional[list] = None
    ) -> Tuple[float, List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Solucionador Combinatório Exato da Mochila 0-1 para Turno de Flesh and Blood (arXiv:2501.11683).
        Avalia o espaço de partição (Ataque, Pitch, Excedente) sobre mão + arsenal (<= 5 cartas).
        Garante que restrições de custo, pitch e Action Points sejam rigorosamente satisfeitas,
        encontrando a sequência ótima global de dano e valor tático V*(H).

        Retorna:
          (max_value, best_attacks, best_pitches, surplus_cards)
        """
        all_cards = list(hand or [])
        if arsenal:
            for ac in arsenal:
                if isinstance(ac, dict):
                    all_cards.append({**ac, "from_arsenal": True})

        if not all_cards:
            return 0.0, [], [], []

        cards_db = _get_cards_db()
        parsed_cards = []
        for idx, c in enumerate(all_cards):
            c_name = str(c.get("cardNumber") or c.get("name", "")).lower()
            c_meta = cards_db.get(c_name, {})
            c_power = int(c.get("power", c_meta.get("power", 0) or 0))
            c_cost = int(c.get("cost", c_meta.get("cost", 0) or 0))
            c_pitch = int(c.get("pitch", c_meta.get("pitch", 1) or 1))
            has_ga = bool(c.get("has_go_again", c_meta.get("has_go_again", False)))
            is_from_ars = bool(c.get("from_arsenal", False))
            has_on_hit = any(oh in c_name for oh in DANGEROUS_ON_HITS)

            # Regra CR 3.1.5: Cartas no Arsenal não podem dar pitch
            can_pitch = not is_from_ars and c_pitch > 0

            # Valor ofensivo intrínseco
            atk_val = float(c_power) + (2.5 if has_ga else 0.0) + (1.5 if has_on_hit else 0.0)

            parsed_cards.append({
                "raw": c,
                "name": c_name,
                "power": c_power,
                "cost": c_cost,
                "pitch": c_pitch,
                "has_ga": has_ga,
                "can_pitch": can_pitch,
                "can_attack": (c_power > 0 or has_ga),
                "is_from_arsenal": is_from_ars,
                "value": atk_val,
                "idx": idx
            })

        n = len(parsed_cards)
        max_comb_value = 0.0
        best_attacks: List[Dict[str, Any]] = []
        best_pitches: List[Dict[str, Any]] = []
        best_surplus: List[Dict[str, Any]] = []

        # Para cada subconjunto de cartas atacantes (2^n combinações)
        for r_atk in range(1, n + 1):
            for atk_combo in itertools.combinations(range(n), r_atk):
                atks = [parsed_cards[i] for i in atk_combo]

                # 1. Validação de capacidade de ataque
                if any(not a["can_attack"] for a in atks):
                    continue

                # 2. Validação de Action Points (AP):
                # Ataques sem Go Again consomem 1 AP cada.
                # O número de ataques sem Go Again não pode exceder base_ap.
                non_ga_count = sum(1 for a in atks if not a["has_ga"])
                if non_ga_count > base_ap:
                    continue

                # Se houver múltiplos ataques, pelo menos (len - 1) devem ter Go Again
                if len(atks) > base_ap and non_ga_count > base_ap:
                    continue

                total_cost = sum(a["cost"] for a in atks)
                cost_needed = max(0, total_cost - floating_res)

                # Cartas restantes candidatas a pitch
                rem_indices = [i for i in range(n) if i not in atk_combo]
                pitch_candidates = [parsed_cards[i] for i in rem_indices if parsed_cards[i]["can_pitch"]]

                # Encontrar subconjunto de pitch viável de menor custo (poupando cartas para surplus)
                viable_pitch_found = False
                chosen_pitches: List[Dict[str, Any]] = []

                if cost_needed == 0:
                    viable_pitch_found = True
                    chosen_pitches = []
                else:
                    # Ordena do maior pitch para o menor para minimizar consumo de cartas
                    pitch_candidates.sort(key=lambda x: x["pitch"], reverse=True)
                    acc_pitch = 0
                    cur_p = []
                    for pc in pitch_candidates:
                        acc_pitch += pc["pitch"]
                        cur_p.append(pc)
                        if acc_pitch >= cost_needed:
                            viable_pitch_found = True
                            chosen_pitches = cur_p
                            break

                if not viable_pitch_found:
                    continue

                comb_val = sum(a["value"] for a in atks)
                # Bônus para cadeias completas e conservação de cartas
                used_indices = set(atk_combo) | {p["idx"] for p in chosen_pitches}
                surplus = [parsed_cards[i] for i in range(n) if i not in used_indices]

                # Desempate favorece: maior valor de dano, mais cartas excedentes poupadas
                score_metric = comb_val + (len(surplus) * 0.1)
                if score_metric > max_comb_value or (max_comb_value == 0.0 and comb_val > 0.0):
                    max_comb_value = score_metric
                    best_attacks = atks
                    best_pitches = chosen_pitches
                    best_surplus = surplus

        real_val = sum(a["value"] for a in best_attacks)
        return real_val, best_attacks, best_pitches, best_surplus

    def calculate_card_opportunity_cost(self, hand: list, card_candidate: dict, floating_res: int = 0) -> float:
        """
        Calcula o Custo de Oportunidade Tático de uma carta (Felt Table & AI Unsheathed).
        Mede a perda de conversão ofensiva V*(H) - V*(H \\ {c}) se a carta for gasta em defesa.
        """
        if not hand or not card_candidate:
            return 0.0

        v_full, _, _, _ = self.solve_knapsack_turn(hand, floating_res=floating_res)
        if v_full <= 0.0:
            return 0.0

        # Remove apenas a primeira ocorrência da carta candidata
        c_target_id = str(card_candidate.get("cardNumber") or card_candidate.get("name", "")).lower()
        sub_hand = []
        removed = False
        for c in hand:
            c_name = str(c.get("cardNumber") or c.get("name", "")).lower()
            if not removed and c_name == c_target_id:
                removed = True
            else:
                sub_hand.append(c)

        v_sub, _, _, _ = self.solve_knapsack_turn(sub_hand, floating_res=floating_res)
        return max(0.0, float(v_full - v_sub))

    def calculate_hand_conversion_potential(self, hand: list, floating_res: int = 0) -> Tuple[float, Set[str]]:
        """
        Calcula o potencial ofensivo de dano e sinergia que a mão atual consegue converter
        utilizando o Solucionador Combinatório Exato Knapsack (arXiv:2501.11683).
        Retorna (potencial_total, conjunto_de_cartas_chave_reservadas).
        """
        if not hand:
            return 0.0, set()

        max_val, attacks, pitches, _ = self.solve_knapsack_turn(hand, floating_res=floating_res)
        if max_val <= 0.0:
            return 0.0, set()

        reserved = {str(a["name"]) for a in attacks} | {str(p["name"]) for p in pitches}
        return max_val, reserved

    def should_trigger_survival_block(
        self,
        my_hp: int,
        opp_power: int,
        is_fatal: bool,
        has_dangerous_on_hit: bool,
        hand: list = None,
        floating_res: int = 0,
        survival_hp_threshold: int = 6
    ) -> bool:
        """
        Determina se o herói DEVE entrar em SURVIVAL_BLOCK estrito.
        Não força bloqueio cego se:
          - A vida estiver saudável (my_hp > 12)
          - O dano não for fatal
          - A conversão ofensiva da mão superar o dano recebido + on-hit
          - O bloqueio exigiria queimar múltiplas cartas com block baixo (<= 2).
        """
        if is_fatal or my_hp <= survival_hp_threshold:
            return True

        if not has_dangerous_on_hit:
            return False

        # Se há on-hit perigoso e vida saudável (> 12), avalia conversão da mão
        if my_hp > 12 and hand:
            hand_conv, _ = self.calculate_hand_conversion_potential(hand, floating_res)
            cards_db = _get_cards_db()
            block_vals = [
                int(c.get("block", c.get("defense", cards_db.get(str(c.get("cardNumber") or c.get("name", "")).lower(), {}).get("block", 0))) or 0)
                for c in hand
            ]
            sorted_b = sorted([b for b in block_vals if b > 0], reverse=True)
            acc = 0
            cards_needed = 0
            for b in sorted_b:
                acc += b
                cards_needed += 1
                if acc >= opp_power:
                    break

            absorb_mult = self.get_dynamic_multiplier("absorb_tempo_bonus", 1.0)
            if cards_needed >= 2 and (hand_conv * absorb_mult) >= (float(opp_power) + 3.5):
                return False

        return opp_power >= 4

    def analyze_turn_plan(self, state: dict) -> TurnPlan:
        """
        Analisa o estado atual (mão, arsenal, vida, recursos, poder inimigo)
        e formula o TurnPlan com avaliação flexível de conversão de mão vs bloqueio.
        """
        my_hp = int(state.get("playerHealth", 20))
        hand = state.get("playerHand", [])
        active_chain = state.get("activeChainLink") or {}
        opp_power = int(active_chain.get("totalPower", state.get("combatChainPower", 0)))
        incoming_name = str(active_chain.get("cardNumber", "")).lower()

        is_fatal = (my_hp - opp_power) <= 0
        has_dangerous_on_hit = any(oh in incoming_name for oh in DANGEROUS_ON_HITS)

        floating_res = int(state.get("playerPitchCount", 0))
        if floating_res == 0:
            resources = state.get("playerResources", [0, 0])
            floating_res = int(resources[0]) if isinstance(resources, list) and resources else 0

        # 1. Modo Sobrevivência Flexível: avalia letalidade e valor
        if self.should_trigger_survival_block(my_hp, opp_power, is_fatal, has_dangerous_on_hit, hand, floating_res):
            return TurnPlan(
                plan_type="SURVIVAL_BLOCK",
                can_absorb_damage=False,
                max_block_cards=len(hand),
                reason="Critical HP, fatal attack or unavoidable on-hit: blocking with available resources"
            )

        # 2. Avaliação de Conversão Ofensiva da Mão (Hand Conversion vs Inefficient Block)
        hand_conversion, key_cards = self.calculate_hand_conversion_potential(hand, floating_res)
        cards_db = _get_cards_db()
        block_values = [
            int(c.get("block", c.get("defense", cards_db.get(str(c.get("cardNumber") or c.get("name", "")).lower(), {}).get("block", 0))) or 0)
            for c in hand
        ]
        sorted_blocks = sorted([b for b in block_values if b > 0], reverse=True)
        acc_block = 0
        cards_needed_to_block = 0
        for b in sorted_blocks:
            acc_block += b
            cards_needed_to_block += 1
            if acc_block >= opp_power:
                break

        on_hit_penalty = 3.5 if has_dangerous_on_hit else 0.0
        absorb_mult = self.get_dynamic_multiplier("absorb_tempo_bonus", 1.0)

        # Condição de Absorção Inteligente (Início/Meio de jogo com vida saudável):
        # Se bloquear consumiria 2 ou mais cartas da mão e a conversão ofensiva supera o dano
        if my_hp > 12 and cards_needed_to_block >= 2 and opp_power > 0:
            if (hand_conversion * absorb_mult) >= (float(opp_power) + on_hit_penalty):
                max_allowed_blocks = max(0, len(hand) - len(key_cards))
                return TurnPlan(
                    plan_type="TEMPO_COUNTER_ATTACK",
                    reserved_card_names=key_cards,
                    can_absorb_damage=True,
                    max_block_cards=min(1, max_allowed_blocks),
                    offensive_potential=hand_conversion,
                    reason=f"Hand offensive conversion ({hand_conversion:.1f}) exceeds inefficient block ({opp_power} dmg needing {cards_needed_to_block} cards); absorbing to counter-attack"
                )

        # 3. Generic Pivot Check
        if my_hp >= 12 and not has_dangerous_on_hit and hand:
            best_attack = None
            best_pitch = None
            max_attack_power = -1

            for c in hand:
                c_name = str(c.get("cardNumber") or c.get("name", "")).lower()
                c_power = int(c.get("power", 0))
                c_cost = int(c.get("cost", 0))
                c_pitch = int(c.get("pitch", 1))
                has_ga = bool(c.get("has_go_again", False))

                if c_power >= 5 or (c_power >= 4 and has_ga):
                    needed_pitch = max(0, c_cost - floating_res)
                    candidate_pitch = None
                    for p in hand:
                        if p is c:
                            continue
                        p_pitch = int(p.get("pitch", 1))
                        if p_pitch >= needed_pitch:
                            candidate_pitch = p
                            break
                    if needed_pitch == 0 or candidate_pitch is not None:
                        potential = float(c_power) + (2.0 if has_ga else 0.0)
                        if potential > max_attack_power:
                            max_attack_power = potential
                            best_attack = c
                            best_pitch = candidate_pitch

            if best_attack is not None and max_attack_power >= opp_power + 2:
                reserved: Set[str] = {str(best_attack.get("cardNumber") or best_attack.get("name", ""))}
                if best_pitch is not None:
                    reserved.add(str(best_pitch.get("cardNumber") or best_pitch.get("name", "")))
                max_blocks = max(0, len(hand) - len(reserved))
                return TurnPlan(
                    plan_type="GENERIC_PIVOT",
                    reserved_card_names=reserved,
                    can_absorb_damage=True,
                    max_block_cards=max_blocks,
                    offensive_potential=max_attack_power,
                    reason=f"Strong attack line ({list(reserved)[0]}) ready; absorbing damage to counter-attack"
                )

        # 4. Fallback: Troca de valor
        return TurnPlan(
            plan_type="VALUE_TRADE",
            can_absorb_damage=False,
            max_block_cards=min(2, len(hand)),
            offensive_potential=0.0,
            reason="Value trade: block cleanly and preserve action tempo"
        )
