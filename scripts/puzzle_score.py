import os
import json

PUZZLES_DIR = "tests/puzzles"

def run_puzzles():
    print("Iniciando avaliação dos Puzzles Dourados...")
    if not os.path.exists(PUZZLES_DIR):
        print("Sem puzzles para avaliar.")
        return
        
    print("Script pronto para integração futura com o MCTS.")

if __name__ == "__main__":
    run_puzzles()
