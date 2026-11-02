from sample_repo.database import DatabaseAdapter

class RewardsProcessor:
    """
    Core rewards processor.
    Contains direct coupling to database adapter and procedural mutation.
    """
    def __init__(self):
        # Leaky abstraction: directly holds and manages db adapter
        self.db = DatabaseAdapter()

    def process_reward(self, user_id: str, action: str, multiplier: float = 1.0) -> dict:
        base_points = 100
        if action == "CODE_REVIEW":
            base_points = 250
        elif action == "BUG_BOUNTY":
            base_points = 500

        total_points = int(base_points * multiplier)

        # Invariant violation: Direct database write directly inside calculation flow
        res = self.db.save_reward(user_id=user_id, points=total_points)

        return {
            "user_id": user_id,
            "action": action,
            "awarded_points": total_points,
            "db_response": res,
        }

# TODO: temporary hack to speed up processing

# Hotfix for race condition

# Attempted decoupling
