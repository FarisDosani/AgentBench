from collections.abc import Callable

from app.models.coding_agent import CodingAgentResult
from app.models.coding_task import CodingTask
from app.models.review import ReviewResult, ReviewerStrategyResult
from app.services.coding_agent_runner import CodingAgentRunner
from app.services.coding_test_runner import CodingTestRunner


Reviewer = Callable[[CodingTask, str], ReviewResult]


class ReviewerStrategy:
    strategy_name = "reviewer"

    def __init__(
        self,
        primary_agent: CodingAgentRunner,
        reviewer: Reviewer,
        test_runner: CodingTestRunner,
        max_review_rounds: int = 1,
    ) -> None:
        if max_review_rounds < 0:
            raise ValueError("max_review_rounds must be non-negative")
        self.primary_agent = primary_agent
        self.reviewer = reviewer
        self.test_runner = test_runner
        self.max_review_rounds = max_review_rounds

    def run(self, task: CodingTask) -> ReviewerStrategyResult:
        baseline = self.test_runner.run_baseline(task)
        agent_results = [self.primary_agent.run(task)]
        reviews: list[ReviewResult] = []
        revision_count = 0

        while agent_results[-1].success:
            review = self.reviewer(task, self._change_summary(agent_results))
            reviews.append(review)
            if review.approved or not review.requested_changes:
                break
            if revision_count >= self.max_review_rounds:
                break

            feedback = (
                f"Reviewer feedback: {review.feedback}\nRequested changes:\n- "
                + "\n- ".join(review.requested_changes)
            )
            agent_results.append(self.primary_agent.run(task, extra_context=feedback))
            revision_count += 1

        test_result = self.test_runner.run_after_changes(task, baseline)
        approved = bool(reviews) and reviews[-1].approved
        success = (
            all(result.success for result in agent_results)
            and approved
            and test_result.all_passed
            and not test_result.regression_detected
        )
        return ReviewerStrategyResult(
            strategy_name=self.strategy_name,
            task_id=task.id,
            agent_results=agent_results,
            reviews=reviews,
            test_result=test_result,
            success=success,
        )

    @staticmethod
    def _change_summary(agent_results: list[CodingAgentResult]) -> str:
        changed_paths: list[str] = []
        for result in agent_results:
            for call in result.tool_calls:
                if call.success and call.tool_name == "write_file":
                    path = call.arguments.get("relative_path")
                    if isinstance(path, str) and path not in changed_paths:
                        changed_paths.append(path)
        if not changed_paths:
            return "No recorded file changes."
        return "Files changed:\n" + "\n".join(f"- {path}" for path in changed_paths)
