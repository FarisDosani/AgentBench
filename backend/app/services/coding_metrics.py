import difflib

from app.models.coding_agent import CodingAgentResult
from app.models.coding_metrics import CodingMetrics, FailureCategory
from app.models.test_result import CodingTestResult


class CodingMetricsCollector:
    def collect(
        self,
        agent_result: CodingAgentResult,
        test_result: CodingTestResult,
        before_files: dict[str, str],
        after_files: dict[str, str],
        *,
        task_success: bool | None = None,
        reviewer_approved: bool | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        total_tokens: int | None = None,
        estimated_cost_usd: float | None = None,
    ) -> CodingMetrics:
        if task_success is None:
            task_success = (
                agent_result.success
                and test_result.all_passed
                and not test_result.regression_detected
                and reviewer_approved is not False
            )
        patch = self.calculate_patch_metrics(before_files, after_files)
        runtime_ms = agent_result.latency_ms + test_result.visible.duration_ms
        if test_result.hidden is not None:
            runtime_ms += test_result.hidden.duration_ms

        return CodingMetrics(
            task_success=task_success,
            regression_detected=test_result.regression_detected,
            tool_calls=len(agent_result.tool_calls),
            runtime_ms=runtime_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=estimated_cost_usd,
            files_changed=patch["files_changed"],
            lines_added=patch["lines_added"],
            lines_removed=patch["lines_removed"],
            patch_size=patch["patch_size"],
            failure_category=self.classify_failure(
                task_success=task_success,
                agent_result=agent_result,
                test_result=test_result,
                reviewer_approved=reviewer_approved,
            ),
        )

    @staticmethod
    def calculate_patch_metrics(
        before_files: dict[str, str],
        after_files: dict[str, str],
    ) -> dict[str, int]:
        files_changed = 0
        lines_added = 0
        lines_removed = 0

        for path in sorted(set(before_files) | set(after_files)):
            before = before_files.get(path, "")
            after = after_files.get(path, "")
            if path in before_files and path in after_files and before == after:
                continue
            files_changed += 1
            for line in difflib.ndiff(before.splitlines(), after.splitlines()):
                if line.startswith("+ "):
                    lines_added += 1
                elif line.startswith("- "):
                    lines_removed += 1

        return {
            "files_changed": files_changed,
            "lines_added": lines_added,
            "lines_removed": lines_removed,
            "patch_size": lines_added + lines_removed,
        }

    @staticmethod
    def classify_failure(
        *,
        task_success: bool,
        agent_result: CodingAgentResult,
        test_result: CodingTestResult,
        reviewer_approved: bool | None = None,
    ) -> FailureCategory:
        if task_success:
            return FailureCategory.NONE

        error = (agent_result.error or "").lower()
        test_timed_out = test_result.visible.timed_out or (
            test_result.hidden is not None and test_result.hidden.timed_out
        )
        if test_timed_out or "timed out" in error or "timeout" in error:
            return FailureCategory.TIMEOUT
        if "malformed" in error:
            return FailureCategory.MALFORMED_RESPONSE
        if "maximum iterations" in error or "max iterations" in error:
            return FailureCategory.MAX_ITERATIONS
        if not agent_result.success:
            return FailureCategory.AGENT_ERROR
        if any(not call.success for call in agent_result.tool_calls):
            return FailureCategory.TOOL_ERROR
        if test_result.regression_detected:
            return FailureCategory.REGRESSION
        if not test_result.visible_passed:
            return FailureCategory.VISIBLE_TEST_FAILURE
        if test_result.hidden_passed is False:
            return FailureCategory.HIDDEN_TEST_FAILURE
        if reviewer_approved is False:
            return FailureCategory.REVIEWER_REJECTION
        return FailureCategory.UNKNOWN
