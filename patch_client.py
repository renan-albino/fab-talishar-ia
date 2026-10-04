import re

with open('ai/bot_runtime/client.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_func = '''    def submit_sideboard(self):
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

        hero = sub_obj["hero"]
        head = sub_obj["head"]
        chest = sub_obj["chest"]
        arms = sub_obj["arms"]
        legs = sub_obj["legs"]
        weapons = sub_obj["hands"]
        flat_deck = sub_obj["deck"]
        inv = sub_obj["inventory"]

        post_payload = {
            "gameName": self.game_id,
            "playerID": self.player_id,
            "authKey": self.auth_key,
            "submission": json.dumps(sub_obj)
        }

        try:
            res = self.session.post(f"{TALISHAR_API_URL}/APIs/SubmitSideboard.php", json=post_payload, timeout=5.0)
        except TypeError:
            res = self.session.post(f"{TALISHAR_API_URL}/APIs/SubmitSideboard.php", json=post_payload)
        try:
            data = res.json()
            if "error" in data or data.get("status") == "FAIL":
                self.error(f"[ERRO NO SIDEBOARD] {data.get('error') or data.get('deckError')}")
                return False
        except Exception:
            pass

        self.metrics["sideboard_info"] = {
            "hero": hero,
            "equipment": {
                "head": head,
                "chest": chest,
                "arms": arms,
                "legs": legs,
                "weapons": weapons
            },
            "deck_size": len(flat_deck)
        }
        return True'''

new_func = '''    def calculate_sideboard(self):
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
        
        self.metrics["sideboard_info"] = {
            "hero": sub_obj["hero"],
            "equipment": {
                "head": sub_obj["head"],
                "chest": sub_obj["chest"],
                "arms": sub_obj["arms"],
                "legs": sub_obj["legs"],
                "weapons": sub_obj["hands"]
            },
            "deck_size": len(sub_obj["deck"])
        }
        return sub_obj

    def submit_equipment(self):
        sub_obj = self.calculate_sideboard()
        post_payload = {
            "gameName": self.game_id,
            "playerID": self.player_id,
            "authKey": self.auth_key,
            "submission": json.dumps(sub_obj),
            "phase": "equipment"
        }
        return self._do_submit_sideboard(post_payload)

    def submit_deck_phase(self):
        sub_obj = self.calculate_sideboard()
        post_payload = {
            "gameName": self.game_id,
            "playerID": self.player_id,
            "authKey": self.auth_key,
            "submission": json.dumps(sub_obj),
            "phase": "deck"
        }
        return self._do_submit_sideboard(post_payload)

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
            return False'''

if old_func in content:
    content = content.replace(old_func, new_func)
    with open('ai/bot_runtime/client.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Success")
else:
    print("Could not find old function")
