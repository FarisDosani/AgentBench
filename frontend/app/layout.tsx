import type { Metadata } from "next";
import Link from "next/link";

import "./globals.css";

export const metadata: Metadata = {
  title: "AgentBench · Coding-Agent Benchmark",
  description: "Run and compare coding-agent strategies in isolated repositories.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <div className="site-shell">
          <header className="site-header">
            <Link className="brand" href="/" aria-label="AgentBench home">
              <span className="brand-mark" aria-hidden="true">A</span>
              <span>
                <strong>AgentBench</strong>
                <small>Coding agents, measured</small>
              </span>
            </Link>
            <nav aria-label="Primary navigation">
              <Link href="/tasks">Tasks</Link>
              <Link href="/run">Run</Link>
              <Link href="/results">Results</Link>
            </nav>
          </header>
          <main>{children}</main>
          <footer className="site-footer">
            <span>AgentBench</span>
            <span>Deterministic evaluation for coding agents.</span>
          </footer>
        </div>
      </body>
    </html>
  );
}
