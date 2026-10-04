import os
import json
import pytest

PUZZLES_DIR = "tests/puzzles"

def load_puzzles():
    puzzles = []
    if not os.path.exists(PUZZLES_DIR):
        return puzzles
    for root, _, files in os.walk(PUZZLES_DIR):
        for file in files:
            if file.endswith(".json"):
                path = os.path.join(root, file)
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    puzzles.append((path, data))
    return puzzles

@pytest.mark.parametrize("path, puzzle", load_puzzles())
def test_golden_puzzle_structure(path, puzzle):
    assert "setup" in puzzle
    assert "state" in puzzle
    assert "expected_best_action" in puzzle
