import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from bot_client import FabBotClient


class TestSideboardAndStalemate(unittest.TestCase):
    def setUp(self):
        self.client = FabBotClient(
            room_id="test_room",
            deck_url="decks/jarl.json",
            role="host",
            player_name="Bot1"
        )
        self.client.game_id = "test_game"
        self.client.player_id = 1
        self.client.auth_key = "test_auth"

    def test_jarl_legal_weapons_sideboard(self):
        """Valida que Jarl NUNCA equipa uma arma 2H junto com um escudo (CR 2.8.2 e CR 3.0)."""
        import json
        with open("decks/jarl.json") as f:
            deck_data = json.load(f)
        raw_cards = deck_data.get("cards", [])

        raw_weapon_candidates = []
        for c in raw_cards:
            cid = c.get("identifier", "")
            meta = self.client.get_card_meta(cid)
            slot = meta.get("slot", "Deck")
            if slot in ("Weapon", "Off-Hand") or meta.get("type") == "W":
                raw_weapon_candidates.append(cid)

        w_2h = []
        w_1h = []
        offhands = []

        for cid in raw_weapon_candidates:
            meta = self.client.get_card_meta(cid)
            slot = meta.get("slot", "")
            subtype = str(meta.get("subtype", "")).lower()
            is_1h = bool(meta.get("is1h", False))
            is_off = (slot == "Off-Hand" or "off-hand" in subtype or "shield" in subtype)
            if is_off:
                offhands.append(cid)
            elif is_1h:
                w_1h.append(cid)
            else:
                w_2h.append(cid)

        self.assertIn("sledge_of_anvilheim", w_2h)
        self.assertIn("titans_fist", w_1h)
        self.assertIn("stalagmite_bastion_of_isenloft", offhands)
        self.assertIn("rampart_of_the_rams_head", offhands)

        # Regra de Loadout Legal
        chosen_weapons = []
        inv = []
        if w_1h and offhands:
            best_off = offhands[0]
            for off in offhands:
                if "stalagmite" in off:
                    best_off = off
                    break
            chosen_weapons = [w_1h[0], best_off]
        elif len(w_1h) >= 2:
            chosen_weapons = [w_1h[0], w_1h[1]]
        elif w_2h:
            chosen_weapons = [w_2h[0]]

        for cid in raw_weapon_candidates:
            if cid not in chosen_weapons:
                inv.append(cid)

        self.assertEqual(len(chosen_weapons), 2)
        self.assertEqual(chosen_weapons[0], "titans_fist")
        self.assertEqual(chosen_weapons[1], "stalagmite_bastion_of_isenloft")
        # Sledge of Anvilheim (2H) DEVE ir para o inventário, NUNCA emparelhado com escudo!
        self.assertIn("sledge_of_anvilheim", inv)
        self.assertNotIn("sledge_of_anvilheim", chosen_weapons)

    def test_2h_weapon_only_sideboard(self):
        """Se o deck tiver apenas uma arma 2H e um escudo (sem arma 1H), o escudo não pode ser equipado."""
        raw_weapon_candidates = ["sledge_of_anvilheim", "rampart_of_the_rams_head"]
        w_2h = []
        w_1h = []
        offhands = []

        for cid in raw_weapon_candidates:
            meta = self.client.get_card_meta(cid)
            slot = meta.get("slot", "")
            subtype = str(meta.get("subtype", "")).lower()
            is_1h = bool(meta.get("is1h", False))
            is_off = (slot == "Off-Hand" or "off-hand" in subtype or "shield" in subtype)
            if is_off:
                offhands.append(cid)
            elif is_1h:
                w_1h.append(cid)
            else:
                w_2h.append(cid)

        chosen_weapons = []
        inv = []
        if w_1h and offhands:
            chosen_weapons = [w_1h[0], offhands[0]]
        elif len(w_1h) >= 2:
            chosen_weapons = [w_1h[0], w_1h[1]]
        elif w_2h:
            chosen_weapons = [w_2h[0]]

        for cid in raw_weapon_candidates:
            if cid not in chosen_weapons:
                inv.append(cid)

        self.assertEqual(chosen_weapons, ["sledge_of_anvilheim"])
        self.assertIn("rampart_of_the_rams_head", inv)

    def test_stalemate_detection_fatigue_draw(self):
        """Valida que quando ambos os decks esgotam e não há mudança de vida por 3 turnos, encerra como Empate."""
        state_fatigue_1 = {
            "turnNo": 25,
            "turnPhase": "M",
            "playerHealth": 14,
            "opponentHealth": 12,
            "playerDeckCount": 0,
            "opponentDeckCount": 0,
            "playerHand": [{"cardNumber": "card1"}],
            "opponentHand": [{"cardNumber": "card2"}],
            "playerArsenal": [],
            "opponentArsenal": [],
        }
        self.client.handle_game_tick(state_fatigue_1)
        self.assertEqual(self.client.metrics["status"], "Jogando")

        # Turno 26 sem alteração de vida (1º turno estagnado)
        state_fatigue_2 = dict(state_fatigue_1, turnNo=26)
        self.client.handle_game_tick(state_fatigue_2)
        self.assertEqual(self.client.metrics["status"], "Jogando")

        # Turno 27 sem alteração de vida (2º turno estagnado)
        state_fatigue_3 = dict(state_fatigue_1, turnNo=27)
        self.client.handle_game_tick(state_fatigue_3)
        self.assertEqual(self.client.metrics["status"], "Jogando")

        # Turno 28 sem alteração de vida (3º turno estagnado com deck 0) -> DEVE finalizar como Empate
        state_fatigue_4 = dict(state_fatigue_1, turnNo=28)
        self.client.handle_game_tick(state_fatigue_4)
        self.assertEqual(self.client.metrics["status"], "Finalizada")

    def test_immediate_deadlock_when_hands_and_decks_empty(self):
        """Valida encerramento imediato se ambos os decks e mãos estão totalmente vazios (sem ações possíveis)."""
        client_empty = FabBotClient(
            room_id="test_deadlock",
            deck_url="decks/jarl.json",
            role="host",
            player_name="Bot1"
        )
        state_deadlock = {
            "turnNo": 20,
            "turnPhase": "M",
            "playerHealth": 10,
            "opponentHealth": 8,
            "playerDeckCount": 0,
            "opponentDeckCount": 0,
            "playerHand": [],
            "opponentHand": [],
            "playerArsenal": [],
            "opponentArsenal": [],
        }
        client_empty.handle_game_tick(state_deadlock)
        self.assertEqual(client_empty.metrics["status"], "Finalizada")

    def test_stalemate_detection_hard_turn_cap(self):
        """Valida o Hard Cap de turnos para evitar loops infinitos."""
        client_blitz = FabBotClient(
            room_id="test_blitz",
            deck_url="decks/ira_blitz.json",
            role="host",
            player_name="Bot1"
        )
        client_blitz.deck_format = "blitz"
        state_turn_46 = {
            "turnNo": 46,
            "turnPhase": "M",
            "playerHealth": 8,
            "opponentHealth": 10,
            "playerDeckCount": 5,
            "opponentDeckCount": 5,
        }
        client_blitz.handle_game_tick(state_turn_46)
        self.assertEqual(client_blitz.metrics["status"], "Finalizada")


if __name__ == "__main__":
    unittest.main()
