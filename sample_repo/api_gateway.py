from sample_repo.rewards_processor import RewardsProcessor

class ApiGateway:
    def __init__(self):
        self.processor = RewardsProcessor()

    def handle_reward_request(self, user_id: str, event_type: str) -> dict:
        return self.processor.process_reward(user_id=user_id, action=event_type)
