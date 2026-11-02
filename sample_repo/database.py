# Database persistence adapter
class DatabaseAdapter:
    def __init__(self):
        self.records = {}

    def save_reward(self, user_id: str, points: int):
        self.records[user_id] = self.records.get(user_id, 0) + points
        return {"status": "SAVED", "user_id": user_id, "balance": self.records[user_id]}
