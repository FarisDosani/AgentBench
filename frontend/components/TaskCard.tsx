import Link from "next/link";

import type { CodingTaskMetadata } from "@/lib/types";

interface TaskCardProps {
  task: CodingTaskMetadata;
}

export function TaskCard({ task }: TaskCardProps) {
  return (
    <article className="card task-card">
      <div className="card-heading">
        <div>
          <p className="eyebrow">{task.id}</p>
          <h2>{task.name}</h2>
        </div>
        <span className={`badge difficulty-${task.difficulty}`}>
          {task.difficulty}
        </span>
      </div>

      <p className="card-description">{task.description}</p>

      <dl className="task-facts">
        <div>
          <dt>Timeout</dt>
          <dd>{task.timeout_seconds}s</dd>
        </div>
        <div>
          <dt>Category</dt>
          <dd>{task.metadata.category ?? "coding"}</dd>
        </div>
      </dl>

      <div className="tag-section">
        <span className="field-label">Allowed tools</span>
        <div className="tag-list">
          {task.allowed_tools.map((tool) => (
            <span className="tag" key={tool}>
              {tool}
            </span>
          ))}
        </div>
      </div>

      {task.expected_files_changed.length > 0 && (
        <div className="tag-section">
          <span className="field-label">Expected files</span>
          <div className="tag-list">
            {task.expected_files_changed.map((file) => (
              <code className="file-chip" key={file}>
                {file}
              </code>
            ))}
          </div>
        </div>
      )}

      <Link className="button button-secondary full-width" href={`/run?task=${encodeURIComponent(task.id)}`}>
        Run this task
        <span aria-hidden="true">→</span>
      </Link>
    </article>
  );
}
