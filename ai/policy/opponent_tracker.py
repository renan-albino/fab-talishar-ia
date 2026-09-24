class OpponentTracker:
    def __init__(self, alpha: float = 0.3):
        self.alpha = alpha
        self.avg_cards_played = 0.0
        self.avg_damage = 0.0
        self.turns_recorded = 0

    def update(self, cards_played: int, damage_dealt: int):
        if self.turns_recorded == 0:
            self.avg_cards_played = float(cards_played)
            self.avg_damage = float(damage_dealt)
        else:
            self.avg_cards_played = self.alpha * cards_played + (1 - self.alpha) * self.avg_cards_played
            self.avg_damage = self.alpha * damage_dealt + (1 - self.alpha) * self.avg_damage
        self.turns_recorded += 1
