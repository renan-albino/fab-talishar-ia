import re

with open('ai/bot_runtime/lobby_manager.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace client.submit_sideboard() at start with nothing, as we wait for the loop.
content = content.replace('    client.submit_sideboard()\n', '')

# We will inject the phase logic directly into the while loops.
def inject_logic(loop_body_regex):
    return re.sub(
        r'# 2\. Se o bot ainda não submeteu sideboard ou o sideboard foi resetado\s*if not data\.get\(\"mySideboardSubmitted\", False\):\s*if not client\.submit_sideboard\(\):\s*sideboard_fail_count \+= 1\s*if sideboard_fail_count >= 3:\s*client\.error\(f\"\[LOBBY ERRO\] Falha repetida no sideboard \(\{sideboard_fail_count\}x\)\. Abortando lobby da sala #\{client\.game_id\}\.\"\)\s*return False\s*time\.sleep\(0\.2\)',
        r'''# 2. Submissão em duas etapas: Equipamento depois Sideboard
                if data.get("canSubmitEquipment", False) and not data.get("myEquipmentSubmitted", False):
                    if not client.submit_equipment():
                        sideboard_fail_count += 1
                        if sideboard_fail_count >= 3:
                            return False
                    time.sleep(0.2)
                elif data.get("canSubmitSideboard", False) and not data.get("mySideboardSubmitted", False):
                    if not client.submit_deck_phase():
                        sideboard_fail_count += 1
                        if sideboard_fail_count >= 3:
                            return False
                    time.sleep(0.2)''',
        loop_body_regex
    )

content = inject_logic(content)

# For wait_for_opponent_and_start, it has a similar block, but maybe with ldata instead of data
content = re.sub(
    r'if not ldata\.get\(\"mySideboardSubmitted\", False\):\s*if not client\.submit_sideboard\(\):\s*sideboard_fail_count \+= 1\s*if sideboard_fail_count >= 3:\s*client\.error\(f\"\[LOBBY ERRO\] Falha repetida no sideboard \(\{sideboard_fail_count\}x\)\. Abortando lobby da sala #\{client\.game_id\}\.\"\)\s*return False\s*time\.sleep\(0\.2\)',
    r'''if ldata.get("canSubmitEquipment", False) and not ldata.get("myEquipmentSubmitted", False):
                        if not client.submit_equipment():
                            sideboard_fail_count += 1
                            if sideboard_fail_count >= 3:
                                return False
                        time.sleep(0.2)
                    elif ldata.get("canSubmitSideboard", False) and not ldata.get("mySideboardSubmitted", False):
                        if not client.submit_deck_phase():
                            sideboard_fail_count += 1
                            if sideboard_fail_count >= 3:
                                return False
                        time.sleep(0.2)''',
    content
)

with open('ai/bot_runtime/lobby_manager.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Patched lobby_manager!")
