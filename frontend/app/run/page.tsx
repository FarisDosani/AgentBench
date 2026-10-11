import { Suspense } from "react";

import { BenchmarkForm } from "@/components/BenchmarkForm";

export default function RunPage() {
  return (
    <section className="page-section narrow-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Live evaluation</p>
          <h1>Run a benchmark</h1>
        </div>
        <p>
          Choose a repository task, provider, and strategy. Execution happens on the
          API server inside isolated Docker workspaces.
        </p>
      </div>
      <Suspense fallback={<div className="loading-panel">Loading benchmark form…</div>}>
        <BenchmarkForm />
      </Suspense>
    </section>
  );
}
