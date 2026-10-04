import sys

with open('ai/bot_runtime/client.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace submit_sideboard entirely
import re

start_idx = content.find("    def submit_sideboard(self):")
if start_idx == -1:
    print("Could not find submit_sideboard")
    sys.exit(1)

end_idx = content.find("    def send_chat_log", start_idx)
if end_idx == -1:
    print("Could not find end of submit_sideboard")
    sys.exit(1)

new_code = '''    def _calculate_sideboard(self):
        if hasattr(self, '_cached_sideboard') and self._cached_sideboard:
            return self._cached_sideboard
        from ai.sideboard_manager import resolve_sideboard
        opp_hero, opp_class = self.get_opponent_info()
        sub_obj = resolve_sideboard(
            deck_url=self.deck_url,
            deck_format=self.deck_format,
            opp_hero=opp_hero,
            opp_class=opp_class,
            get_card_meta=self.get_card_meta,
            log_fn=self.log,
            game_id=self.game_id or "",
            player_id=self.player_id or 1,
        )
        self._cached_sideboard = sub_obj
        return sub_obj

    def submit_equipment(self):
        sub_obj = self._calculate_sideboard()
        post_payload = {
            "gameName": self.game_id,
            "playerID": self.player_id,
            "authKey": self.auth_key,
            "submission": json.dumps(sub_obj),
            "phase": "equipment"
        }
        return self._do_submit_sideboard(post_payload)

    def submit_deck_phase(self):
        sub_obj = self._calculate_sideboard()
        post_payload = {
            "gameName": self.game_id,
            "playerID": self.player_id,
            "authKey": self.auth_key,
            "submission": json.dumps(sub_obj),
            "phase": "deck"
        }
        success = self._do_submit_sideboard(post_payload)
        
        if success:
            hero = sub_obj["hero"]
            flat_deck = sub_obj["deck"]
            inv = sub_obj["inventory"]
            self.metrics["sideboard_info"] = {
                "hero": hero,
                "equipment": {
                    "head": sub_obj["head"],
                    "chest": sub_obj["chest"],
                    "arms": sub_obj["arms"],
                    "legs": sub_obj["legs"],
                    "weapons": sub_obj["hands"]
                },
                "main_deck_count": len(flat_deck),
                "main_deck_cards": flat_deck,
                "sideboard_count": len(inv),
                "sideboard_cards": inv
            }
            self.save_metrics_throttled(force=True)

            from ai.policy_engine import PolicyEngine
            import os
            self.policy_engine = PolicyEngine(
                hero_name=hero,
                model_path="data/model_latest.pt" if os.path.exists("data/model_latest.pt") else None,
                device="cuda",
                log_fn=self.log
            )
            self.log(f"[LOBBY] AI Policy Engine inicializado para {hero}.")
        return success

    def _do_submit_sideboard(self, post_payload):
        try:
            res = self.session.post(f"{TALISHAR_API_URL}/APIs/SubmitSideboard.php", json=post_payload, timeout=5.0)
        except TypeError:
            res = self.session.post(f"{TALISHAR_API_URL}/APIs/SubmitSideboard.php", json=post_payload)
        try:
            data = res.json()
            if "error" in data or data.get("status") == "FAIL":
                self.error(f"[ERRO NO SIDEBOARD] {data.get('error') or data.get('deckError')}")
                return False
            return True
        except Exception:
            pass
        return True

'''

content = content[:start_idx] + new_code + content[end_idx:]

with open('ai/bot_runtime/client.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Replaced successfully!")
