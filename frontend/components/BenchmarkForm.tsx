"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";

import { StrategyResultCard } from "@/components/StrategyResultCard";
import { getCodingTasks, runCodingBenchmark } from "@/lib/api";
import type {
  CodingBenchmarkResponse,
  CodingTaskMetadata,
  Provider,
  StrategyName,
} from "@/lib/types";

const STRATEGIES: Array<{ value: StrategyName; label: string; detail: string }> = [
  { value: "direct", label: "Direct", detail: "Single focused agent loop" },
  {
    value: "planner_executor",
    label: "Planner / Executor",
    detail: "Plan first, then execute",
  },
  { value: "reviewer", label: "Reviewer", detail: "Solve, review, and revise" },
];

export function BenchmarkForm() {
  const searchParams = useSearchParams();
  const requestedTask = searchParams.get("task");
  const [tasks, setTasks] = useState<CodingTaskMetadata[]>([]);
  const [taskId, setTaskId] = useState("");
  const [provider, setProvider] = useState<Provider>("openrouter");
  const [model, setModel] = useState("openai/gpt-4o-mini");
  const [strategies, setStrategies] = useState<StrategyName[]>(["direct"]);
  const [maxIterations, setMaxIterations] = useState(20);
  const [keepWorkspaces, setKeepWorkspaces] = useState(false);
  const [loadingTasks, setLoadingTasks] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<CodingBenchmarkResponse | null>(null);

  useEffect(() => {
    let active = true;
    getCodingTasks()
      .then((items) => {
        if (!active) return;
        setTasks(items);
        const selected = items.some((task) => task.id === requestedTask)
          ? requestedTask
          : items[0]?.id;
        setTaskId(selected ?? "");
      })
      .catch((reason: unknown) => {
        if (active) {
          setError(reason instanceof Error ? reason.message : "Could not load tasks.");
        }
      })
      .finally(() => {
        if (active) setLoadingTasks(false);
      });
    return () => {
      active = false;
    };
  }, [requestedTask]);

  const selectedTask = useMemo(
    () => tasks.find((task) => task.id === taskId),
    [taskId, tasks],
  );

  function toggleStrategy(strategy: StrategyName) {
    setStrategies((current) =>
      current.includes(strategy)
        ? current.filter((item) => item !== strategy)
        : [...current, strategy],
    );
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!taskId || !model.trim()) {
      setError("Choose a task and enter a model ID.");
      return;
    }
    if (strategies.length === 0) {
      setError("Select at least one strategy.");
      return;
    }

    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const response = await runCodingBenchmark({
        task_id: taskId,
        provider,
        model: model.trim(),
        strategies,
        max_iterations: maxIterations,
        keep_workspaces: keepWorkspaces,
      });
      setResult(response);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Benchmark run failed.");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="run-layout">
      <form className="card benchmark-form" onSubmit={handleSubmit}>
        <div className="form-heading">
          <div>
            <p className="eyebrow">Configuration</p>
            <h2>Benchmark setup</h2>
          </div>
          <span className="secure-note">Keys stay on the API server</span>
        </div>

        <label className="field">
          <span>Task</span>
          <select
            value={taskId}
            onChange={(event) => setTaskId(event.target.value)}
            disabled={loadingTasks || running}
            required
          >
            {loadingTasks && <option>Loading tasks…</option>}
            {!loadingTasks && tasks.length === 0 && <option>No tasks available</option>}
            {tasks.map((task) => (
              <option key={task.id} value={task.id}>
                {task.name} · {task.difficulty}
              </option>
            ))}
          </select>
        </label>

        {selectedTask && (
          <div className="selected-task-note">
            <span className={`badge difficulty-${selectedTask.difficulty}`}>
              {selectedTask.difficulty}
            </span>
            <span>{selectedTask.description}</span>
          </div>
        )}

        <div className="form-grid">
          <label className="field">
            <span>Provider</span>
            <select
              value={provider}
              onChange={(event) => setProvider(event.target.value as Provider)}
              disabled={running}
            >
              <option value="openrouter">OpenRouter</option>
              <option value="gemini">Gemini</option>
              <option value="omniroute">OmniRoute</option>
            </select>
          </label>

          <label className="field">
            <span>Model</span>
            <input
              value={model}
              onChange={(event) => setModel(event.target.value)}
              disabled={running}
              placeholder="Provider model ID"
              required
            />
          </label>
        </div>

        <fieldset className="strategy-fieldset" disabled={running}>
          <legend>Strategies</legend>
          <div className="strategy-options">
            {STRATEGIES.map((strategy) => (
              <label className="strategy-option" key={strategy.value}>
                <input
                  type="checkbox"
                  checked={strategies.includes(strategy.value)}
                  onChange={() => toggleStrategy(strategy.value)}
                />
                <span>
                  <strong>{strategy.label}</strong>
                  <small>{strategy.detail}</small>
                </span>
              </label>
            ))}
          </div>
        </fieldset>

        <div className="form-grid align-end">
          <label className="field">
            <span>Max iterations</span>
            <input
              type="number"
              min={1}
              value={maxIterations}
              onChange={(event) => setMaxIterations(Number(event.target.value))}
              disabled={running}
              required
            />
          </label>

          <label className="toggle-field">
            <input
              type="checkbox"
              checked={keepWorkspaces}
              onChange={(event) => setKeepWorkspaces(event.target.checked)}
              disabled={running}
            />
            <span>
              <strong>Keep workspaces</strong>
              <small>Preserve local copies for backend debugging</small>
            </span>
          </label>
        </div>

        {error && (
          <div className="alert alert-error" role="alert">
            {error}
          </div>
        )}

        <button
          className="button button-primary run-button"
          type="submit"
          disabled={running || loadingTasks || tasks.length === 0}
        >
          {running ? (
            <>
              <span className="spinner" aria-hidden="true" />
              Running benchmark…
            </>
          ) : (
            <>
              Run benchmark <span aria-hidden="true">→</span>
            </>
          )}
        </button>
      </form>

      {result && (
        <section className="results-section" aria-live="polite">
          <div className="section-heading compact-heading">
            <div>
              <p className="eyebrow">Completed run</p>
              <h2>Strategy results</h2>
              <p>
                {result.task_id} · {result.difficulty}
              </p>
            </div>
            {result.best_strategy && (
              <span className="run-best">
                Best: {result.best_strategy.replaceAll("_", " / ")}
              </span>
            )}
          </div>
          <div className="result-list">
            {result.strategy_results.map((strategyResult) => (
              <StrategyResultCard
                key={strategyResult.strategy_name}
                result={strategyResult}
                isBest={result.best_strategy === strategyResult.strategy_name}
              />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
