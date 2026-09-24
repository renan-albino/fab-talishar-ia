import sys

def patch():
    with open('/home/renan/fab-talishar-ia/ai/game_simulator.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # Find the methods
    attack_start = content.find('    @classmethod\n    def simulate_attack')
    defense_start = content.find('    @classmethod\n    def simulate_defense')
    pitch_start = content.find('    @classmethod\n    def simulate_pitch')
    step_start = content.find('    @classmethod\n    def simulate_step')

    new_attack = '''    @classmethod
    def simulate_attack(cls, state, action: dict):
        """
        Simula a execução de um ataque na fase principal (Phase M).
        Aplica desconto de pitch conforme CR 1.14.2, AP, buffs de equipamento,
        poder de combate vs bloqueio do oponente e vida.
        """
        if not isinstance(state, ImmutableGameState):
            state = ImmutableGameState(state)
            
        updates = {}
        act_type = str(action.get("type", "hand")).lower()
        act_name = str(action.get("cardNumber") or action.get("name") or "").lower().strip()

        if act_type in ("equipment_ability", "weapon_buff", "hero_ability"):
            buff_power = int(action.get("buff_power", 4 if "hammerhead" in act_name else (2 if "goliath" in act_name else 1)))
            updates["currentAttackBuff"] = int(state.get("currentAttackBuff", 0)) + buff_power
            ap = int(state.get("playerAP", state.get("actionPoints", 1)))
            has_go_again = bool(action.get("has_go_again", False))
            new_ap = ap if has_go_again else max(0, ap - 1)
            updates["playerAP"] = new_ap
            updates["actionPoints"] = new_ap
            return state.without("_simulated_projected_damage").replace(**updates)

        hand = list(state.get("playerHand", []))
        pitch_zone = list(state.get("playerPitch", []))
        discard_zone = list(state.get("playerDiscard", []))

        played_card = None
        if act_type == "hand":
            new_hand = []
            for c in hand:
                if played_card is None and cls.extract_card_meta(c)["name"] == act_name:
                    played_card = c
                else:
                    new_hand.append(c)
            hand = new_hand
            updates["playerHand"] = tuple(hand)
            if played_card is None:
                played_card = action.get("raw") or action
        elif act_type == "arsenal":
            ars = state.get("playerArsenal", [])
            updates["playerArsenal"] = tuple([c for c in ars if cls.extract_card_meta(c)["name"] != act_name])
            played_card = action.get("raw") or action
        elif act_type == "banish":
            banish = state.get("playerBanish", [])
            updates["playerBanish"] = tuple([c for c in banish if cls.extract_card_meta(c)["name"] != act_name])
            played_card = action.get("raw") or action
        else:
            played_card = action.get("raw") or action

        card_meta = cls.extract_card_meta(played_card)
        cost = int(action.get("cost", card_meta.get("cost", 0)))

        resources = state.get("playerResources", [0, 0])
        floating = int(resources[0]) if resources and isinstance(resources, (list, tuple)) else 0

        if floating < cost:
            needed = cost - floating
            candidates = [(c, cls.extract_card_meta(c)) for c in hand]
            candidates.sort(key=lambda item: -item[1]["pitch"])
            rem_hand = []
            for c, meta in candidates:
                if needed > 0:
                    floating += meta["pitch"]
                    needed -= meta["pitch"]
                    pitch_zone.append(c)
                else:
                    rem_hand.append(c)
            hand = rem_hand
            updates["playerHand"] = tuple(hand)

        floating = max(0, floating - cost)
        updates["playerResources"] = (floating, 0)

        ap = int(state.get("playerAP", state.get("actionPoints", 1)))
        has_go_again = bool(action.get("has_go_again", card_meta.get("has_go_again", False)))
        new_ap = ap if has_go_again else max(0, ap - 1)
        updates["playerAP"] = new_ap
        updates["actionPoints"] = new_ap

        if act_type == "hand":
            discard_zone.append(played_card)

        updates["playerPitch"] = tuple(pitch_zone)
        updates["playerDiscard"] = tuple(discard_zone)

        atk_buff = int(state.get("currentAttackBuff", 0))
        base_power = int(action.get("power", card_meta.get("power", 4)))
        atk_power = base_power + atk_buff

        updates["combatChainPower"] = atk_power
        active_chain = dict(state.get("activeChainLink", {}))
        if active_chain or state.get("activeChainLink") is not None:
            active_chain["totalPower"] = atk_power
            active_chain["power"] = atk_power
            active_chain["cardNumber"] = act_name
            updates["activeChainLink"] = ImmutableGameState(active_chain)

        opp_hp = int(state.get("opponentHealth", state.get("theirHealth", 40)))
        opp_hand = list(state.get("opponentHand", []))

        raw_intim = action.get("intimidate")
        if raw_intim is None:
            raw_intim = action.get("intimidate_count", card_meta.get("intimidate_count", 0))
        if isinstance(raw_intim, bool):
            intimidate_count = 1 if raw_intim else 0
        elif isinstance(raw_intim, (int, float)):
            intimidate_count = max(0, int(raw_intim))
        elif action.get("has_intimidate") or card_meta.get("has_intimidate"):
            intimidate_count = int(action.get("intimidate_count", card_meta.get("intimidate_count", 1)))
        elif any(k in act_name.lower() for k in ["pack_hunt", "alpha_rampage", "barraging_beatdown", "intimidate"]):
            intimidate_count = int(action.get("intimidate_count", 1))
        else:
            intimidate_count = 0

        if opp_hand and isinstance(opp_hand[0], dict):
            usable_hand = opp_hand[intimidate_count:] if intimidate_count > 0 else opp_hand
            cards_def = [int(c.get("defense", c.get("block", 3))) for c in usable_hand]
            cards_def.sort(reverse=True)
            opp_hand_count = len(usable_hand)

            if opp_hp <= 8:
                expected_block = min(atk_power, sum(cards_def))
                cards_used_to_block = min(opp_hand_count, (expected_block + 2) // 3)
            elif opp_hp <= 18:
                expected_block = min(atk_power, sum(cards_def[:max(1, len(cards_def) // 2)]))
                cards_used_to_block = min(opp_hand_count, (expected_block + 2) // 3)
            else:
                expected_block = min(atk_power, cards_def[0] if cards_def else 0)
                cards_used_to_block = 1 if expected_block > 0 else 0
        else:
            base_hand_count = int(state.get("opponentHandCount", state.get("theirHandCount", 3)))
            opp_hand_count = max(0, base_hand_count - intimidate_count)
            if opp_hp <= 8:
                expected_block = min(atk_power, int(opp_hand_count * 2.8))
                cards_used_to_block = min(opp_hand_count, (expected_block + 2) // 3)
            elif opp_hp <= 18:
                expected_block = min(atk_power, int(opp_hand_count * 1.8))
                cards_used_to_block = min(opp_hand_count, (expected_block + 2) // 3)
            else:
                expected_block = min(atk_power, int(opp_hand_count * 1.0))
                cards_used_to_block = min(opp_hand_count, (expected_block + 2) // 3)

        unblocked_damage = max(0, atk_power - expected_block)
        updates["opponentHealth"] = max(0, opp_hp - unblocked_damage)
        updates["theirHealth"] = max(0, opp_hp - unblocked_damage)

        new_opp_hand = max(0, opp_hand_count - cards_used_to_block)
        
        has_on_hit = bool(action.get("has_on_hit", card_meta.get("has_on_hit", False)))
        if unblocked_damage > 0 and has_on_hit:
            new_opp_hand = max(0, new_opp_hand - 1)

        updates["opponentHandCount"] = new_opp_hand
        updates["theirHandCount"] = new_opp_hand

        return state.without("_simulated_projected_damage", "currentAttackBuff").replace(**updates)
'''

    new_defense = '''    @classmethod
    def simulate_defense(cls, state, block_action: dict):
        """
        Simula a decisão de bloqueio na fase defensiva (Phase B).
        Soma a defesa total de multi-cartas contra o ataque recebido (CR 7.3 e 7.5),
        em vez de deduzir dano líquido por carta individualmente.
        """
        if not isinstance(state, ImmutableGameState):
            state = ImmutableGameState(state)
            
        updates = {}
        my_hp = int(state.get("playerHealth", state.get("yourHealth", 20)))
        active_chain = dict(state.get("activeChainLink", {}))
        
        incoming_power = int(active_chain.get("totalPower", active_chain.get("power", state.get("combatChainPower", 4))))

        if isinstance(block_action, list):
            cards_to_block = block_action
        elif isinstance(block_action, dict) and "cards" in block_action and isinstance(block_action["cards"], list):
            cards_to_block = block_action["cards"]
        elif isinstance(block_action, dict) and "blocking_cards" in block_action and isinstance(block_action["blocking_cards"], list):
            cards_to_block = block_action["blocking_cards"]
        elif isinstance(block_action, dict) and "card_names" in block_action and isinstance(block_action["card_names"], list):
            cards_to_block = block_action["card_names"]
        else:
            cards_to_block = [block_action]

        hand = list(state.get("playerHand", []))
        discard = list(state.get("playerDiscard", []))

        action_def = 0
        for c in cards_to_block:
            if isinstance(c, dict):
                c_meta = cls.extract_card_meta(c)
                val = int(c.get("defense", c.get("block", c_meta.get("defense", 0))))
                c_name = str(c.get("name") or c.get("cardNumber") or c_meta.get("name", "")).lower()
            else:
                c_name = str(c).lower()
                c_meta = cls.extract_card_meta({"cardNumber": c_name})
                val = int(c_meta.get("defense", 0))

            action_def += val

            found_idx = -1
            for idx, h_card in enumerate(hand):
                h_name = cls.extract_card_meta(h_card)["name"]
                if h_name == c_name or str(h_card.get("cardNumber", "")).lower() == c_name:
                    found_idx = idx
                    break
            if found_idx >= 0:
                discard.append(hand.pop(found_idx))

        updates["playerHand"] = tuple(hand)
        updates["playerDiscard"] = tuple(discard)

        prev_def = int(active_chain.get("totalDefense", 0))
        
        projected_damage = int(state.get("_simulated_projected_damage", 0))
        base_hp = my_hp + projected_damage

        total_def = prev_def + action_def
        active_chain["totalDefense"] = total_def
        active_chain["defense"] = total_def
        active_chain["block"] = total_def
        updates["activeChainLink"] = ImmutableGameState(active_chain)

        taken_damage = max(0, incoming_power - total_def)
        updates["playerHealth"] = max(0, base_hp - taken_damage)
        updates["yourHealth"] = max(0, base_hp - taken_damage)
        updates["_simulated_projected_damage"] = taken_damage

        return state.replace(**updates)
'''

    new_pitch = '''    @classmethod
    def simulate_pitch(cls, state, pitch_action: dict):
        """
        Simula a geração de recursos na fase de Pitch (Phase P / PDECK).
        """
        if not isinstance(state, ImmutableGameState):
            state = ImmutableGameState(state)
            
        updates = {}
        resources = state.get("playerResources", [0, 0])
        floating = int(resources[0]) if resources and isinstance(resources, (list, tuple)) else 0
        
        card_name = cls.extract_card_meta(pitch_action)["name"]
        if "pitch" in pitch_action:
            pitch_val = cls._safe_int(pitch_action["pitch"], 0)
        else:
            meta = cls.extract_card_meta(pitch_action)
            pitch_val = meta["pitch"]

        hand = list(state.get("playerHand", []))
        pitch_zone = list(state.get("playerPitch", []))
        new_hand = []
        found = False
        for c in hand:
            if not found and cls.extract_card_meta(c)["name"] == card_name:
                found = True
                pitch_zone.append(c)
            else:
                new_hand.append(c)

        updates["playerHand"] = tuple(new_hand)
        updates["playerPitch"] = tuple(pitch_zone)
        if found:
            updates["playerResources"] = (floating + pitch_val, 0)

        return state.replace(**updates)
'''

    new_step = '''    @classmethod
    def simulate_step(cls, state, action: dict):
        """
        Ponto de entrada unificado para simulação de passo.
        """
        if not isinstance(state, ImmutableGameState):
            state = ImmutableGameState(state)
            
        act_type = str(action.get("type", "")).lower()
        phase = str(state.get("turnPhase", state.get("phase", "M"))).upper()

        if act_type in ("pass", "end_turn", "close_chain", "pass_priority"):
            next_state = state
        elif "block" in act_type or phase in ("B", "DEFENSE"):
            next_state = cls.simulate_defense(state, action)
        elif "pitch" in act_type or phase in ("P", "PDECK"):
            next_state = cls.simulate_pitch(state, action)
        else:
            next_state = cls.simulate_attack(state, action)

        vec = FaBPolicyValueNetwork.extract_state_vector(next_state.to_dict())
        return next_state, vec
'''

    content = content[:attack_start] + new_attack + '\n' + new_defense + '\n' + new_pitch + '\n' + new_step
    with open('/home/renan/fab-talishar-ia/ai/game_simulator.py', 'w', encoding='utf-8') as f:
        f.write(content)

patch()
