import { JobDemo } from "@/components/job-demo";

const layers = [
  { name: "Interface", detail: "Next.js on Vercel", mark: "01" },
  { name: "API", detail: "FastAPI on Render", mark: "02" },
  { name: "Worker", detail: "Durable queue consumer", mark: "03" },
  { name: "Data", detail: "Supabase Postgres + Storage", mark: "04" },
];

export default function Home() {
  return (
    <main>
      <nav className="nav-shell" aria-label="Primary navigation">
        <a className="wordmark" href="#top" aria-label="VendorLens home">
          <span className="wordmark-mark">VL</span>VendorLens
        </a>
        <a className="nav-link" href="#architecture">Architecture</a>
        <a className="nav-link" href="#example">Live example</a>
        <a className="nav-cta" href="https://github.com/ALmcEX/VendorLens">
          View source <span aria-hidden="true">↗</span>
        </a>
      </nav>

      <header className="hero" id="top">
        <div className="hero-copy">
          <div className="eyebrow"><span /> Foundation release · 0.1</div>
          <h1>Evidence infrastructure for clearer vendor review.</h1>
          <p className="hero-lede">
            VendorLens is building a traceable workspace for security and privacy teams evaluating
            AI SaaS vendors. This release proves the delivery system before higher-stakes review
            features arrive.
          </p>
          <div className="hero-actions">
            <a className="primary-action" href="#example">Run the stack <span>↓</span></a>
            <span className="cost-note">Foundation hosting target · about $7/month</span>
          </div>
        </div>
        <div className="signal-card" aria-label="Foundation system status">
          <div className="signal-header">
            <span>System topology</span>
            <span className="live-pill"><i /> READY BY DESIGN</span>
          </div>
          <div className="signal-flow">
            {layers.map((layer, index) => (
              <div className="flow-row" key={layer.name}>
                <span className="flow-index">{layer.mark}</span>
                <div><strong>{layer.name}</strong><small>{layer.detail}</small></div>
                {index < layers.length - 1 && <span className="flow-line" aria-hidden="true" />}
              </div>
            ))}
          </div>
        </div>
      </header>

      <section className="architecture" id="architecture" aria-labelledby="architecture-title">
        <div>
          <div className="section-kicker">Built for inspectability</div>
          <h2 id="architecture-title">A small, observable foundation.</h2>
        </div>
        <p className="section-copy">
          Each boundary is explicit: typed contracts, durable state, bounded retries, health probes,
          and provider configuration that lives with the code.
        </p>
        <div className="capability-grid">
          <article><span>API</span><h3>Safe request boundaries</h3><p>Validation, idempotency, rate limits, queue guards, and stable Problem Details.</p></article>
          <article><span>ASYNC</span><h3>Durable processing</h3><p>At-least-once delivery with terminal-state checks and inspectable failure categories.</p></article>
          <article><span>OPS</span><h3>Deployment as code</h3><p>One monorepo for application builds, migrations, CI, and hosted-service manifests.</p></article>
        </div>
      </section>

      <section className="example-section" id="example">
        <div className="example-context">
          <div className="section-kicker">Current scope</div>
          <h2>Infrastructure first. Decisions later.</h2>
          <p>
            This foundation is <strong>not a vendor-risk decision system</strong>. It does not accept
            evidence files, score vendors, or make purchasing recommendations.
          </p>
          <ul>
            <li><span>✓</span> Non-sensitive demonstration payloads only</li>
            <li><span>✓</span> Deterministic processing without paid models</li>
            <li><span>✓</span> Public, reviewable application contracts</li>
          </ul>
        </div>
        <JobDemo />
      </section>

      <footer>
        <span>VendorLens · Foundation 0.1</span>
        <span>Security review deserves evidence, not theater.</span>
      </footer>
    </main>
  );
}
