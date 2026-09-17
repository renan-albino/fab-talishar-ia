"""
ai/policy/attack_pruner.py
==========================
Módulo de poda de candidatos de ataque, encadeamento de Go Again e busca MCTS/ISMCTS ofensiva.
"""

from typing import Dict, List, Optional, Any

from .constants import (
    _load_cards_db,
    ALL_FAB_WEAPONS,
    WEAPON_KEYWORDS,
)
from ..hero_strategies import RangerStrategy, RunebladeStrategy
from .card_semantics import parse_card_semantics


def select_best_attack(engine: Any, state: dict, unpayable_set: Optional[set] = None) -> Optional[Dict[str, Any]]:
    """
    Seleciona o melhor candidato de ataque (da mão, equipamento, arma, arsenal, banish, cemitério ou aliados),
    aplicando poda de Action Points, encadeamento de Go Again e refinamento via ISMCTS / MCTS.
    """
    if unpayable_set is None:
        unpayable_set = set()
    turn_plan = engine.strategy.analyze_turn_plan(state)
    floating_res, total_res = engine.calculate_available_resources(state)
    hand = state.get("playerHand", [])
    player_ap = int(state.get("playerAP", state.get("actionPoints", 1)))

    # ── Consciência Semântica de Itens Próprios na Arena (ex: Boom Grenade armada) ──
    my_items = state.get("playerItems") or state.get("myItems") or []
    has_own_on_hit_item = False
    for item in my_items:
        if isinstance(item, dict):
            i_prof = parse_card_semantics(str(item.get("cardNumber", item.get("name", ""))), item)
            if i_prof.extra_on_hit_damage > 0:
                has_own_on_hit_item = True
                break

    candidates = []

    # ── 1.1 Coletar Ações na Mão ────────────────────────────────
    hand_attacks = []
    has_any_go_again = False

    for idx, c in enumerate(hand):
        info = engine.extract_card_info(c)
        c_name = info["name"]
        c_id = info["actionDataOverride"] or str(idx)
        c_action = info["action"] if info["action"] > 0 else 27
        # Regra FaB CR 2.1.2: Cartas de Flecha (Arrow) NUNCA podem ser jogadas diretamente da mão!
        # Elas só podem ser jogadas a partir do Arsenal usando um Arco.
        c_db = _load_cards_db().get(c_name, {})
        c_subtype = str(c_db.get("subtype", "")).lower()
        if "arrow" in c_subtype or "arrow" in c_name:
            continue

        if info["action"] > 0 and c_name not in unpayable_set:
            card_cost = max(0, int(info.get("cost", 0)))
            # A própria carta atacante é gasta e não pode dar pitch para pagar a si mesma!
            # O pitch disponível para esta carta é (total_res - info["pitch"])
            pitch_from_other_cards = total_res - info["pitch"]
            if pitch_from_other_cards >= card_cost:
                base_score = engine.strategy.evaluate_attack_card(
                    c_name, info["power"], card_cost, info["has_go_again"], info["pitch"]
                )
                base_score = engine.strategy.modify_attack_candidate_score(
                    c_name, info, turn_plan, base_score, state
                )

                # ── Ajustes Táticos Baseados no TurnPlan ─────────────────
                c_clean = str(c.get("cardNumber") or c_name).lower()
                if turn_plan.plan_type == "OVERPITCH_RECOVERY" and any(k in c_clean for k in ["codex_of_frailty", "sea_floor_salvage", "tip_the_barkeep"]):
                    base_score += 30.0  # Prioridade máxima: jogar NAA de recuperação para recarregar o arsenal
                elif turn_plan.plan_type == "HARPOON_CHAIN" and any(k in c_clean for k in ["portside_exchange", "three_of_a_kind", "cheating_scoundrel"]):
                    base_score += 20.0  # Buffs antes do disparo do arsenal

                elif "avast_ye" in c_clean:
                    # Avast Ye! concede Go Again ao aliado/ataque e gera Gold no hit!
                    allies = state.get("playerAllies", [])
                    has_ready_allies = any(isinstance(a, dict) and a.get("action", 0) > 0 for a in (allies or []))
                    has_other_attacks = any(
                        engine.extract_card_info(x)["power"] > 0 for x in hand if x != c
                    )
                    discard = state.get("playerDiscard", []) or state.get("playerGraveyard", [])
                    has_grave_allies = any(
                        isinstance(x, dict) and x.get("overlay") != 1 and str(x.get("facing", "")).upper() != "DOWN" and
                        any(k in str(x.get("cardNumber") or "").lower() for k in ["anka", "chum", "riggermortis", "sawbones", "scooba"])
                        for x in discard
                    )
                    if has_ready_allies or has_other_attacks or has_grave_allies:
                        base_score += 30.0  # Prioridade máxima: jogar Avast Ye! antes do aliado/ataque!
                elif ("gravy" in str(engine.hero_name).lower() or getattr(engine.strategy, "is_ally_hero", False)) and any(k in c_clean for k in ["call_to_the_grave", "portside_exchange", "tip_the_barkeep", "loot_the_hold"]):
                    discard = state.get("playerDiscard", []) or state.get("playerGraveyard", [])
                    has_grave_allies = any(
                        isinstance(x, dict) and x.get("overlay") != 1 and str(x.get("facing", "")).upper() != "DOWN" and
                        any(k in str(x.get("cardNumber") or "").lower() for k in ["anka", "chum", "riggermortis", "sawbones", "scooba"])
                        for x in discard
                    )
                    if has_grave_allies:
                        base_score += 25.0  # Enabler azul para ativar Watery Grave no cemitério!
                elif c_name in turn_plan.reserved_card_names or c_clean in turn_plan.reserved_card_names:
                    base_score += 15.0  # Peça chave do plano ofensivo reservada

                if info["has_go_again"]:
                    has_any_go_again = True
                hand_attacks.append({
                    "type": "hand", "idx": idx, "card_id": c_id, "mode": c_action,
                    "name": c_name, "score": base_score, "cost": card_cost,
                    "power": info["power"], "has_go_again": info["has_go_again"],
                    "pitch": info["pitch"]
                })

    # ── 1.2 Poda Tática de Go Again (Evitar quebrar a cadeia prematuramente)
    # Se temos AP == 1 e múltiplos ataques na mão, e pelo menos um tem Go Again:
    # Penalizamos severamente iniciar o turno com um ataque SEM Go Again.
    for atk in hand_attacks:
        if player_ap <= 1 and has_any_go_again and not atk["has_go_again"] and len(hand_attacks) > 1:
            # Se não for letal (power < oponente_hp), penaliza iniciar com non-go-again
            atk["score"] -= 4.0
        elif atk["has_go_again"] and atk["cost"] == 0:
            # Bônus para abrir cadeia com starter de custo zero
            atk["score"] += 1.5

        if has_own_on_hit_item:
            # Ataques rápidos ou de alto poder têm prioridade para garantir que o dano extra do item da arena converta
            if atk["has_go_again"] or atk["power"] >= 4 or atk["cost"] == 0:
                atk["score"] += 3.0

        candidates.append(atk)

    # ── 1.3 Equipamentos, Armas e Habilidades de Herói ─────────
    equip = state.get("playerEquipment", [])
    for eq in equip:
        action = eq.get("action", 0)
        eq_name = str(eq.get("cardNumber", "Equip")).lower()
        if action > 0 and eq_name not in unpayable_set:
            eq_id = eq.get("actionDataOverride", eq_name)
            eq_slot = str(eq.get("slot", "")).lower()
            eq_type = str(eq.get("type", "")).upper()

            # 1.3.1 Habilidade Ativa do Herói (Character Ability)
            is_hero = (
                eq_slot == "hero"
                or eq_type == "C"
                or str(eq.get("actionDataOverride", "")) == "0"
                or any(h in eq_name for h in ["marlynn", "kassai", "bravo", "dash", "dorinthea", "rhinar", "kayo", "jarl", "azalea", "riptide", "teklovossen", "vynnset", "hala", "mario", "arakni"])
            )
            if is_hero:
                hero_score = engine.strategy.evaluate_hero_ability(state, eq)
                if hero_score > 0:
                    candidates.append({
                        "type": "hero_ability", "idx": 0, "card_id": str(eq_id), "mode": action,
                        "name": eq_name, "score": hero_score, "cost": 0,
                        "power": 0, "has_go_again": True
                    })
                continue

            # 1.3.2 Armas de Combate e Buffs de Equipamento
            is_weapon = (
                eq_name in ALL_FAB_WEAPONS
                or any(w in eq_name for w in WEAPON_KEYWORDS)
                or eq_slot in ("weapon", "off-hand", "hands")
            )
            if is_weapon:
                weapon_cost = engine.get_weapon_cost(eq_name, eq, state=state)
                is_traditional_bow = (
                    ("bow" in str(_load_cards_db().get(eq_name, {}).get("subtype", "")).lower()
                     or any(b in eq_name for b in ["shiver", "death_dealer", "dread_bore", "dreadbore", "redback", "sandscour"]))
                    and "hammerhead" not in eq_name
                )

                # Poda de arcos tradicionais: só carrega flecha se o Arsenal estiver livre
                if is_traditional_bow:
                    arsenal_cards = state.get("playerArsenal") or state.get("playerArse") or []
                    if isinstance(arsenal_cards, list) and len(arsenal_cards) > 0:
                        continue
                    if turn_plan.plan_type == "DEFENSIVE_TRAP":
                        continue

                # Habilidade especial de arma delegada à estratégia do herói (ex: Hammerhead em MarlynnStrategy)
                weapon_ability_candidate = engine.strategy.evaluate_weapon_ability(
                    eq_name, weapon_cost, state, total_res, turn_plan=turn_plan
                )
                if weapon_ability_candidate is not None:
                    if weapon_ability_candidate:  # Não foi podada pela estratégia
                        weapon_ability_candidate["idx"] = 0
                        weapon_ability_candidate["card_id"] = str(eq_id)
                        weapon_ability_candidate["mode"] = action
                        candidates.append(weapon_ability_candidate)
                    continue

                # Poda de Symbiosis Shot: requer 1+ steam counters para poder atacar
                if "symbiosis" in eq_name:
                    steam_counters = int(eq.get("counters", eq.get("steam_counters", 0)))
                    if steam_counters <= 0:
                        continue

                # Teklo Leveler: igual com 0 e 1 Evos (custo 3), escala com 2+ Evos
                evos_equipped = 0
                if "leveler" in eq_name or "teklo_leveler" in eq_name:
                    equip_list = state.get("playerEquipment", []) if state else []
                    evos_equipped = sum(1 for e in equip_list if isinstance(e, dict) and ("evo" in str(e.get("cardNumber", "")).lower() or "evo" in str(e.get("subtype", "")).lower()))

                # Armas convencionais de ataque
                if total_res >= weapon_cost:
                    eq_info = engine.extract_card_info(eq)
                    weapon_power = eq_info.get("power", 0) or int(eq.get("power", 0))
                    if weapon_power == 0:
                        weapon_power = int(_load_cards_db().get(eq_name, {}).get("power", 0))

                    weapon_has_ga = False
                    if "leveler" in eq_name or "teklo_leveler" in eq_name:
                        if evos_equipped >= 3:
                            weapon_has_ga = True
                        if evos_equipped >= 4:
                            weapon_power = 3
                        else:
                            weapon_power = 2

                    try:
                        weapon_score = engine.strategy.evaluate_weapon_attack(
                            eq_name, floating_res, total_res, len(hand_attacks) > 0,
                            state=state, evos_equipped=evos_equipped
                        )
                    except TypeError:
                        weapon_score = engine.strategy.evaluate_weapon_attack(
                            eq_name, floating_res, total_res, len(hand_attacks) > 0
                        )
                    if not has_any_go_again and len(hand_attacks) == 0:
                        weapon_score += 2.0
                    if is_traditional_bow:
                        weapon_score += 8.0
                    candidates.append({
                        "type": "weapon", "idx": 0, "card_id": str(eq_id), "mode": action,
                        "name": eq_name, "score": weapon_score, "cost": weapon_cost,
                        "power": weapon_power, "has_go_again": weapon_has_ga
                    })
                continue

            # 1.3.3 Habilidade Ativada de Equipamento (Head, Chest, Arms, Legs, Off-Hand)
            is_equipment_slot = (
                eq_slot in ("head", "chest", "arms", "legs", "off-hand", "equipment")
                or eq_type == "E"
            ) and not is_weapon and not is_hero

            if is_equipment_slot:
                eq_cost = engine.get_weapon_cost(eq_name, eq, state=state)
                if total_res >= eq_cost:
                    eq_score = engine.strategy.evaluate_equipment_ability(state, eq, hand_attacks=hand_attacks)
                    if eq_score > 0:
                        candidates.append({
                            "type": "equipment_ability",
                            "idx": 0,
                            "card_id": str(eq_id),
                            "mode": action,
                            "name": eq_name,
                            "score": eq_score,
                            "cost": eq_cost,
                            "power": 0,
                            "has_go_again": True
                        })

    # ── 1.4 Arsenal e Banish ────────────────────────────────────
    # Contagem de tokens/auras de Runechant para o desconto oficial de Runegate
    runechant_count = 0
    for aura in (state.get("playerAuras") or []):
        if isinstance(aura, dict) and "runechant" in str(aura.get("cardNumber") or aura.get("name", "")).lower():
            runechant_count += max(1, int(aura.get("counters", aura.get("count", 1))))
    for token in (state.get("playerTokens") or []):
        if isinstance(token, dict) and "runechant" in str(token.get("cardNumber") or token.get("name", "")).lower():
            runechant_count += max(1, int(token.get("counters", token.get("count", 1))))
    if "playerRunechants" in state:
        try:
            runechant_count = max(runechant_count, int(state.get("playerRunechants", 0)))
        except Exception:
            pass

    for zone_name, key in [("Arsenal", "playerArsenal"), ("Banish", "playerBanish"), ("Graveyard", "playerGraveyard")]:
        zone = state.get(key) or (state.get("playerArse", []) if key == "playerArsenal" else (state.get("playerDiscard", []) if key == "playerGraveyard" else []))
        for idx, c in enumerate(zone):
            if not isinstance(c, dict):
                continue
            action = c.get("action", 0)
            c_name = str(c.get("cardNumber", "Card")).lower()
            # Regra Oficial FaB / Talishar: Aliados mortos no cemitério virados para baixo (face-down / overlay: 1) NÃO podem ser jogados
            if zone_name == "Graveyard":
                is_down = c.get("overlay") == 1 or str(c.get("facing", "")).upper() == "DOWN"
                if is_down:
                    continue
            if action > 0 and c_name not in unpayable_set:
                c_id = c.get("actionDataOverride") or str(c.get("uniqueID", idx))
                c_info = engine.extract_card_info(c)
                card_cost = max(0, int(c_info.get("cost", 0)))
                effective_cost = card_cost

                # No FaB oficial, Runegate permite jogar do Banish destruindo Runechants em vez de pagar recursos
                # Regra FaB: apenas cartas de ATAQUE possuem Runegate (fasting_carcass NÃO possui Runegate)
                if zone_name == "Banish":
                    db_c = _load_cards_db().get(c_name, {})
                    is_runegate = (
                        any(k in c_name for k in [
                            "cull", "deathly", "widespread",
                            "oblivion", "beseech", "runegate"
                        ])
                        or "runegate" in str(db_c.get("text", "")).lower()
                        or "runegate" in str(c.get("text", "")).lower()
                    )
                    if is_runegate:
                        effective_cost = max(0, card_cost - runechant_count)

                # Cartas de Arsenal/Banish/Graveyard usam total_res da mão inteira (ou effective_cost de Runegate)
                if total_res >= effective_cost:
                    base_score = engine.strategy.evaluate_attack_card(
                        c_name, c_info["power"], effective_cost, c_info["has_go_again"], c_info["pitch"]
                    )
                    has_ga = c_info["has_go_again"]
                    is_instant = False

                    if zone_name == "Banish":
                        # Jogar do Banish alivia Blood Debt e projeta dano alto
                        play_score = base_score + 10.0
                        if isinstance(engine.strategy, RunebladeStrategy) or "vynnset" in str(engine.hero_name).lower():
                            play_score += 15.0  # Vynnset quer esvaziar o Banish para não morrer de Blood Debt
                        # Regra oficial: equipar Evo da zona banida é jogado como Instant se permitido pelo herói (Teklovossen)
                        if "evo" in c_name:
                            if "singularity" not in c_name:
                                if not engine.strategy.can_play_banished_card(c_name, c_info, state):
                                    continue  # Habilidade inativa: Evo permanece banido e inerte!
                            is_instant = True
                            has_ga = True  # Instant resolve sem consumir Action Point
                            play_score += 12.0
                        if "singularity" in c_name:
                            play_score += 35.0  # Mechropotent Singularity é o finalizador absoluto
                    elif zone_name == "Graveyard":
                        # Cartas jogáveis do cemitério (ex: Instant liberada por Astral Bridge ou recursão de cartas)
                        play_score = base_score + 18.0
                        if getattr(engine.strategy, "is_ally_hero", False) or "gravy" in str(engine.hero_name).lower():
                            play_score += 15.0  # Gravy Bones prioriza recursão de aliados face-up do cemitério
                        db_entry = _load_cards_db().get(c_name, {})
                        c_type = str(c_info.get("type") or db_entry.get("type", "")).upper()
                        if c_type == "I" or "instant" in c_type.lower() or action == 27:
                            is_instant = True
                            has_ga = True
                    else:
                        # Jogar do Arsenal executa a ofensiva e libera o slot para o canhão carregar nova flecha
                        play_score = base_score + 4.0
                        # Se a carta no Arsenal for uma Non-Attack Action (ex: Portside Exchange, Codex of Frailty):
                        # Jogar do Arsenal PRIMEIRO libera o slot e concede bônus antes do disparo!
                        c_type = str(_load_cards_db().get(c_name, {}).get("type", "")).upper()
                        is_naa = ("AA" not in c_type and "ATTACK" not in c_type) or any(k in c_name for k in ["portside", "codex", "salvage", "three_of_a_kind", "tip_the_barkeep"])
                        if is_naa:
                            play_score += 15.0  # Prioridade máxima: jogue a NAA do arsenal para liberar o slot!
                            if turn_plan.plan_type == "OVERPITCH_RECOVERY":
                                play_score += 15.0
                        elif any(k in c_name for k in ["arrow", "harpoon", "bolt", "trophy"]) or isinstance(engine.strategy, RangerStrategy):
                            play_score += 10.0  # Flecha carregada no arsenal pronta para disparo!
                            if turn_plan.plan_type == "HARPOON_CHAIN":
                                play_score += 15.0

                    candidate_item = {
                        "type": zone_name.lower(), "idx": idx, "card_id": str(c_id), "mode": action,
                        "name": c_name, "score": play_score, "cost": effective_cost,
                        "power": c_info["power"], "has_go_again": has_ga
                    }
                    if is_instant:
                        candidate_item["is_instant"] = True
                        candidate_item["ap_cost"] = 0
                    candidates.append(candidate_item)

    # ── 1.5 Aliados em Jogo (playerAllies) ───────────────────────
    allies = state.get("playerAllies", [])
    if isinstance(allies, list):
        for idx, ally in enumerate(allies):
            if not isinstance(ally, dict):
                continue
            action = ally.get("action", 0)
            a_name = str(ally.get("cardNumber") or ally.get("name", "")).lower()
            if action > 0 and a_name not in unpayable_set:
                a_id = ally.get("actionDataOverride") or str(ally.get("uniqueID", idx))
                a_info = engine.extract_card_info(ally)
                ability_cost = int(_load_cards_db().get(a_name, {}).get("ability_cost", 0))
                if total_res >= ability_cost:
                    ally_power = a_info.get("power", 0) or int(_load_cards_db().get(a_name, {}).get("power", 0))
                    base_score = float(ally_power) * 2.0
                    if getattr(engine.strategy, "is_ally_hero", False) or "gravy" in str(engine.hero_name).lower():
                        base_score += 15.0  # Gravy Bones valoriza ataques de aliados agressivamente
                        # Se temos Avast Ye! na mão e AP <= 1, jogue Avast Ye! PRIMEIRO para conceder Go Again ao aliado!
                        has_avast = any("avast_ye" in str(h.get("cardNumber") or h.get("name", "")).lower() for h in state.get("playerHand", []))
                        if player_ap <= 1 and has_avast:
                            base_score -= 20.0  # Dá prioridade a Avast Ye! para conceder Go Again e continuar a cadeia
                        else:
                            # Se o oponente está na zona crítica (<= 6 HP), priorizar aliados pesados para perfurar o bloco
                            opp_h = int(state.get("opponentHealth", state.get("oppHealth", 40)))
                            if opp_h <= 6:
                                if ally_power >= opp_h:
                                    base_score += 15.0  # Golpe de misericórdia letal direto
                                elif ally_power >= 4:
                                    base_score += 10.0  # Quebrador de defesa que força múltiplos bloqueios
                    candidates.append({
                        "type": "ally", "idx": idx, "card_id": str(a_id), "mode": action,
                        "name": a_name, "score": base_score, "cost": ability_cost,
                        "power": ally_power, "has_go_again": False
                    })

    if player_ap <= 0:
        # Se não possui Action Points disponíveis, apenas ações Instantâneas (custo 0 de AP) podem ser jogadas
        candidates = [c for c in candidates if c.get("is_instant") is True or c.get("ap_cost") == 0]

    if not candidates:
        return None

    # ── 1.6 Refinamento via Busca em Árvore ─────────────────────
    if len(candidates) > 1 and engine.num_mcts_sims > 0:
        opp_hand = state.get("opponentHand", [])
        if isinstance(opp_hand, list) and len(opp_hand) > 0:
            opp_hand_count = len(opp_hand)
        else:
            opp_hand_count = int(
                state.get("opponentHandCount", state.get("theirHandCount", 0))
            )

        # Usa ISMCTS quando o oponente tem cartas na mão (informação imperfeita real)
        if opp_hand_count > 0:
            best_idx, policy_dist, ismcts_log = engine.ismcts.search_ismcts(
                state=state,
                legal_actions=candidates,
                num_simulations=engine.num_mcts_sims,
            )
            # Enriquece a ação escolhida com metadados ISMCTS para logging no bot
            chosen = candidates[best_idx]
            chosen["_ismcts_log"] = ismcts_log
            chosen["_policy_dist"] = policy_dist

            # ── Persistência de Telemetria ISMCTS Direta ──────────
            try:
                engine.ismcts_logger.log(
                    ismcts_log=ismcts_log,
                    turn=int(state.get("turnNo", state.get("turn", 0))),
                    phase=str(state.get("turnPhase", state.get("phase", "M"))),
                )
            except Exception:
                pass

            return chosen
        else:
            # MCTS clássico: estado de informação completa (mão do oponente vazia / início de turno)
            best_mcts_idx, policy_dist = engine.mcts.search(
                state=state,
                legal_actions=candidates,
                num_simulations=engine.num_mcts_sims,
            )
            chosen = candidates[best_mcts_idx]
            chosen["_policy_dist"] = policy_dist
            return chosen

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[0]
