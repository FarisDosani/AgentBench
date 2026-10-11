export type TaskDifficulty = "easy" | "medium" | "hard";
export type Provider = "gemini" | "openrouter" | "omniroute";
export type StrategyName = "direct" | "planner_executor" | "reviewer";

export interface CodingTaskMetadata {
  id: string;
  name: string;
  description: string;
  difficulty: TaskDifficulty;
  allowed_tools: string[];
  timeout_seconds: number;
  expected_files_changed: string[];
  metadata: Record<string, string>;
}

export interface CodingBenchmarkRequest {
  task_id: string;
  provider: Provider;
  model: string;
  strategies: StrategyName[];
  max_iterations: number;
  keep_workspaces: boolean;
}

export interface SafeCodingTestSummary {
  visible_passed: boolean;
  hidden_passed: boolean | null;
  all_passed: boolean;
  regression_detected: boolean;
}

export type FailureCategory =
  | "none"
  | "agent_error"
  | "timeout"
  | "tool_error"
  | "visible_test_failure"
  | "hidden_test_failure"
  | "regression"
  | "malformed_response"
  | "max_iterations"
  | "reviewer_rejection"
  | "unknown";

export interface CodingMetrics {
  task_success: boolean;
  regression_detected: boolean;
  tool_calls: number;
  runtime_ms: number;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  total_tokens: number | null;
  estimated_cost_usd: number | null;
  files_changed: number;
  lines_added: number;
  lines_removed: number;
  patch_size: number;
  failure_category: FailureCategory;
}

export interface StrategyBenchmarkResult {
  strategy_name: string;
  task_id: string;
  success: boolean;
  test_summary: SafeCodingTestSummary;
  metrics: CodingMetrics;
}

export interface CodingBenchmarkResponse {
  task_id: string;
  difficulty: TaskDifficulty;
  strategy_results: StrategyBenchmarkResult[];
  best_strategy: string | null;
}
