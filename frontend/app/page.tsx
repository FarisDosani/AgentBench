import Link from "next/link";

const CAPABILITIES = [
  {
    number: "01",
    title: "Isolated execution",
    text: "Every strategy works inside its own Docker-confined repository copy.",
  },
  {
    number: "02",
    title: "Three strategies",
    text: "Compare Direct, Planner / Executor, and Reviewer workflows on one task.",
  },
  {
    number: "03",
    title: "Rigorous validation",
    text: "Visible and hidden tests reveal correctness while regression checks protect behavior.",
  },
  {
    number: "04",
    title: "Useful metrics",
    text: "Track runtime, tool use, patch size, changed files, tokens, and failure category.",
  },
];

export default function HomePage() {
  return (
    <>
      <section className="hero">
        <div className="hero-copy">
          <div className="status-pill">
            <span aria-hidden="true" /> Evaluation system online
          </div>
          <p className="eyebrow">Coding-Agent Benchmark</p>
          <h1>Measure the work,<br />not the pitch.</h1>
          <p className="hero-lede">
            AgentBench runs coding agents against realistic repository tasks, checks
            their work in isolation, and turns every attempt into comparable evidence.
          </p>
          <div className="hero-actions">
            <Link className="button button-primary" href="/tasks">
              Browse tasks <span aria-hidden="true">→</span>
            </Link>
            <Link className="button button-secondary" href="/run">
              Run benchmark
            </Link>
          </div>
        </div>

        <div className="hero-panel" aria-label="Benchmark workflow preview">
          <div className="terminal-bar">
            <span /><span /><span />
            <code>agentbench / run</code>
          </div>
          <div className="terminal-content">
            <p><span className="terminal-prompt">$</span> strategy direct</p>
            <div className="terminal-step"><span>01</span><strong>Repository copied</strong><em>ready</em></div>
            <div className="terminal-step"><span>02</span><strong>Agent patch applied</strong><em>+12 −4</em></div>
            <div className="terminal-step"><span>03</span><strong>Visible tests</strong><em className="pass">passed</em></div>
            <div className="terminal-step"><span>04</span><strong>Hidden tests</strong><em className="pass">passed</em></div>
            <div className="terminal-result">
              <span>Task success</span><strong>TRUE</strong>
            </div>
          </div>
        </div>
      </section>

      <section className="capability-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Evidence over intuition</p>
            <h2>A controlled loop from task to verdict.</h2>
          </div>
          <p>Provider-neutral orchestration with deterministic evaluation and concise reporting.</p>
        </div>
        <div className="capability-grid">
          {CAPABILITIES.map((capability) => (
            <article className="capability-card" key={capability.number}>
              <span>{capability.number}</span>
              <h3>{capability.title}</h3>
              <p>{capability.text}</p>
            </article>
          ))}
        </div>
      </section>
    </>
  );
}
