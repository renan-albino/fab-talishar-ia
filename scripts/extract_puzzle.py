import sys
import json
import os
import argparse
from stats.db import get_connection

def extract(room_id, turn, hero, slug):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT pre_state_json, card_id FROM shadow_steps WHERE room_id = ? AND turn = ?", (room_id, turn))
        rows = cursor.fetchall()
        if not rows:
            print("Nenhum registro encontrado em shadow_steps para esta match/turno.")
            return
        
        row = rows[0]
        if not row["pre_state_json"]:
            print("pre_state_json não armazenado (talvez não era contra humano).")
            return
            
        pre_state = json.loads(row["pre_state_json"])
        best_action = row["card_id"]
        
        out = {
            "setup": {"hero": hero, "match": room_id, "turn": turn},
            "state": pre_state,
            "expected_best_action": {"type": "play", "card_id": best_action}
        }
        
        d = f"tests/puzzles/{hero.lower().replace(' ', '_')}"
        os.makedirs(d, exist_ok=True)
        path = f"{d}/{slug}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)
        print(f"Puzzle extraído para {path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("room", help="Room ID")
    parser.add_argument("turn", type=int, help="Turn number")
    parser.add_argument("hero", help="Hero name")
    parser.add_argument("slug", help="File slug")
    args = parser.parse_args()
    extract(args.room, args.turn, args.hero, args.slug)
