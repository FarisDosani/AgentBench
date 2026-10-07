from app.models.benchmark import BenchmarkRunResult
from app.models.comparison import AgentComparisonSummary, ComparisonResult


class ComparisonService:
    def compare(self, runs: list[BenchmarkRunResult]) -> ComparisonResult:
        ranked_runs = sorted(
            runs,
            key=lambda run: (
                -run.average_score,
                run.average_latency_ms,
                run.agent_name,
            ),
        )

        summaries = [
            AgentComparisonSummary(
                rank=rank,
                agent_name=run.agent_name,
                average_score=run.average_score,
                average_latency_ms=run.average_latency_ms,
                passed_tasks=run.passed_tasks,
                failed_tasks=run.failed_tasks,
                total_tasks=run.total_tasks,
            )
            for rank, run in enumerate(ranked_runs, start=1)
        ]

        if not summaries:
            return ComparisonResult(
                summaries=[],
                best_agent=None,
                report="AgentBench Comparison Report\n\nNo benchmark runs available.",
            )

        report_sections = ["AgentBench Comparison Report"]
        for summary in summaries:
            report_sections.append(
                "\n".join(
                    [
                        f"{summary.rank}. {summary.agent_name}",
                        f"Score: {summary.average_score:.2f}",
                        f"Latency: {summary.average_latency_ms:.2f} ms",
                        f"Passed: {summary.passed_tasks}/{summary.total_tasks}",
                    ]
                )
            )

        best_agent = summaries[0].agent_name
        report_sections.append(f"Best Agent: {best_agent}")

        return ComparisonResult(
            summaries=summaries,
            best_agent=best_agent,
            report="\n\n".join(report_sections),
        )
