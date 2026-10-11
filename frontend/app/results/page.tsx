import Link from "next/link";

export default function ResultsPage() {
  return (
    <section className="page-section narrow-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Run output</p>
          <h1>Results</h1>
        </div>
        <p>Review strategy outcomes immediately after each coding benchmark run.</p>
      </div>

      <div className="card empty-results">
        <div className="empty-icon" aria-hidden="true">↗</div>
        <h2>Coding results appear after a run</h2>
        <p>
          AgentBench does not expose coding-result persistence yet. Run a benchmark
          to inspect its safe test summary and metrics in the current view.
        </p>
        <Link className="button button-primary" href="/run">
          Configure a benchmark <span aria-hidden="true">→</span>
        </Link>
      </div>
    </section>
  );
}
