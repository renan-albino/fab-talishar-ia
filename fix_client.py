import re

with open("ai/bot_runtime/client.py", "r", encoding="utf-8") as f:
    content = f.read()

# Replace imports
content = content.replace("from ai.common import safe_int, safe_list, safe_dict, safe_str", "from ai.common.schemas import GameState")

# Replace safe_* wrappers in handle_game_tick and decide_and_act
content = re.sub(r'safe_int\(([^,)]+)(,\s*default=[^)]+)?\)', r'\1', content)
content = re.sub(r'safe_list\(([^,)]+)\)', r'\1', content)
content = re.sub(r'safe_dict\(([^,)]+)\)', r'\1', content)
content = re.sub(r'safe_str\(([^,)]+)(,\s*default=[^)]+)?\)', r'\1', content)

# Inject GameState parser into handle_game_tick
old_handle_game_tick = """    def handle_game_tick(self, state: dict):
        if not isinstance(state, dict):
            return"""
new_handle_game_tick = """    def handle_game_tick(self, state: dict):
        if not isinstance(state, dict):
            return
            
        try:
            parsed_state = GameState(**state)
            state.update(parsed_state.model_dump())
        except Exception:
            pass"""
content = content.replace(old_handle_game_tick, new_handle_game_tick)

# Inject GameState parser into decide_and_act
old_decide_and_act = """    def decide_and_act(self, state: dict):
        if not isinstance(state, dict):
            return False"""
new_decide_and_act = """    def decide_and_act(self, state: dict):
        if not isinstance(state, dict):
            return False
            
        try:
            parsed_state = GameState(**state)
            state.update(parsed_state.model_dump())
        except Exception:
            pass"""
content = content.replace(old_decide_and_act, new_decide_and_act)

with open("ai/bot_runtime/client.py", "w", encoding="utf-8") as f:
    f.write(content)
