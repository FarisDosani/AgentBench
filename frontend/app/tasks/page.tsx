"use client";

import { useEffect, useState } from "react";

import { TaskCard } from "@/components/TaskCard";
import { getCodingTasks } from "@/lib/api";
import type { CodingTaskMetadata } from "@/lib/types";

export default function TasksPage() {
  const [tasks, setTasks] = useState<CodingTaskMetadata[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    getCodingTasks()
      .then((items) => {
        if (active) setTasks(items);
      })
      .catch((reason: unknown) => {
        if (active) {
          setError(reason instanceof Error ? reason.message : "Could not load tasks.");
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <section className="page-section">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Benchmark catalog</p>
          <h1>Coding tasks</h1>
        </div>
        <p>
          Repository-level challenges across three difficulty tiers. Each task runs
          against visible and protected hidden validation.
        </p>
      </div>

      {loading && <div className="loading-panel">Loading benchmark tasks…</div>}
      {error && <div className="alert alert-error" role="alert">{error}</div>}
      {!loading && !error && tasks.length === 0 && (
        <div className="empty-state">No coding tasks are currently available.</div>
      )}
      <div className="task-grid">
        {tasks.map((task) => <TaskCard key={task.id} task={task} />)}
      </div>
    </section>
  );
}
