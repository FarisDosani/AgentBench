from pydantic import BaseModel

from app.models.coding_agent import CodingAgentResult
from app.models.test_result import CodingTestResult


class StrategyResult(BaseModel):
    strategy_name: str
    task_id: str
    agent_result: CodingAgentResult
    test_result: CodingTestResult
    success: bool
