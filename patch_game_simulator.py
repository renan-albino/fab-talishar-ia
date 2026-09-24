import re

with open('ai/game_simulator.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Remove _shallow_clone_state
content = re.sub(r'import copy\ndef _shallow_clone_state\(.*?\n    return cloned\n+', '', content, flags=re.DOTALL)

# Add import at the top of GameSimulator
if 'from ai.mcts.state import ImmutableGameState' not in content:
    content = content.replace('class GameSimulator:', 'from ai.mcts.state import ImmutableGameState\n\nclass GameSimulator:')

with open('ai/game_simulator.py', 'w', encoding='utf-8') as f:
    f.write(content)
