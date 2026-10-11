import { MetricsGrid } from "@/components/MetricsGrid";
import type { StrategyBenchmarkResult } from "@/lib/types";

interface StrategyResultCardProps {
  result: StrategyBenchmarkResult;
  isBest: boolean;
}

function TestState({
  label,
  value,
  passedText = "Passed",
  failedText = "Failed",
}: {
  label: string;
  value: boolean | null;
  passedText?: string;
  failedText?: string;
}) {
  const state = value === null ? "not-run" : value ? "passed" : "failed";
  const text = value === null ? "Not configured" : value ? passedText : failedText;

  return (
    <div className="test-state">
      <span>{label}</span>
      <strong className={`status-text status-${state}`}>
        <span className="status-dot" aria-hidden="true" />
        {text}
      </strong>
    </div>
  );
}

export function StrategyResultCard({ result, isBest }: StrategyResultCardProps) {
  return (
    <article className={`card result-card ${isBest ? "best-result" : ""}`}>
      <div className="card-heading">
        <div>
          <p className="eyebrow">Strategy</p>
          <h3>{result.strategy_name.replaceAll("_", " / ")}</h3>
        </div>
        <div className="badge-row">
          {isBest && <span className="badge badge-best">Best strategy</span>}
          <span className={`badge ${result.success ? "badge-success" : "badge-failure"}`}>
            {result.success ? "Success" : "Failure"}
          </span>
        </div>
      </div>

      <div className="test-summary" aria-label="Test summary">
        <TestState label="Visible tests" value={result.test_summary.visible_passed} />
        <TestState label="Hidden tests" value={result.test_summary.hidden_passed} />
        <TestState label="All tests" value={result.test_summary.all_passed} />
        <TestState
          label="Regression detected"
          value={result.test_summary.regression_detected ? false : true}
          passedText="No"
          failedText="Yes"
        />
      </div>

      <MetricsGrid metrics={result.metrics} />
    </article>
  );
}
