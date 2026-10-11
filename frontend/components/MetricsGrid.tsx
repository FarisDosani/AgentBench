import type { CodingMetrics } from "@/lib/types";

interface MetricsGridProps {
  metrics: CodingMetrics;
}

function formatCost(value: number | null): string {
  return value === null ? "—" : `$${value.toFixed(4)}`;
}

export function MetricsGrid({ metrics }: MetricsGridProps) {
  const entries = [
    ["Task success", metrics.task_success ? "Yes" : "No"],
    ["Tool calls", metrics.tool_calls.toLocaleString()],
    ["Runtime", `${metrics.runtime_ms.toFixed(0)} ms`],
    ["Files changed", metrics.files_changed.toLocaleString()],
    ["Lines added", `+${metrics.lines_added}`],
    ["Lines removed", `−${metrics.lines_removed}`],
    ["Patch size", metrics.patch_size.toLocaleString()],
    ["Failure category", metrics.failure_category.replaceAll("_", " ")],
    ["Prompt tokens", metrics.prompt_tokens?.toLocaleString() ?? "—"],
    ["Completion tokens", metrics.completion_tokens?.toLocaleString() ?? "—"],
    ["Total tokens", metrics.total_tokens?.toLocaleString() ?? "—"],
    ["Estimated cost", formatCost(metrics.estimated_cost_usd)],
  ];

  return (
    <dl className="metrics-grid">
      {entries.map(([label, value]) => (
        <div className="metric" key={label}>
          <dt>{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}
