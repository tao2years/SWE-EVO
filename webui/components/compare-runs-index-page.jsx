import { buildCompareRunsOverview } from "@/lib/dashboard-data";

function safeText(value) {
  return value === null || value === undefined || value === "" ? "n/a" : String(value);
}

function numberish(value) {
  return typeof value === "number" ? value.toLocaleString() : "n/a";
}

function artifactViewerUrl(url) {
  if (!url) {
    return url;
  }
  if (!url.startsWith("/artifact?")) {
    return url;
  }
  const params = new URLSearchParams(url.split("?", 2)[1] || "");
  const path = params.get("path");
  if (!path) {
    return url;
  }
  return `/artifacts?path=${encodeURIComponent(path)}`;
}

function DetailChip({ label, value }) {
  return (
    <span className="detail-chip">
      <span>{label}</span>
      <strong>{value}</strong>
    </span>
  );
}

export default async function CompareRunsIndexPage() {
  const payload = await buildCompareRunsOverview();
  const compareRuns = payload.compareRuns || [];

  return (
    <main className="artifact-shell compare-run-shell">
      <section className="artifact-hero">
        <div>
          <p className="eyebrow">Compare Runs</p>
          <h1>Single-Task CLI Trace Compare</h1>
          <p className="hero-copy artifact-path">
            Serial compare runs from <code>custom_cli_case/compare_runs</code>. Open a task to inspect side-by-side traces.
          </p>
        </div>
      </section>

      <section className="panel compare-panel">
        <div className="artifact-json-header">
          <div>
            <h2>Available Compare Runs</h2>
            <p className="panel-note">Each item compares multiple CLIs on the same task with raw trace artifacts attached.</p>
          </div>
        </div>
        {compareRuns.length ? (
          <div className="compare-run-list">
            {compareRuns.map((item) => (
              <article className="analysis-doc" key={item.compare_id}>
                <div className="analysis-doc-top">
                  <div>
                    <div className="analysis-doc-id">{item.instance_id || item.compare_id}</div>
                    <div className="analysis-doc-meta">
                      {safeText(item.repo)} · {safeText(item.updated_at ? new Date(item.updated_at).toLocaleString() : null)}
                    </div>
                  </div>
                  <div className="analysis-doc-actions">
                    <a className="ghost-button" href={item.detail_url} rel="noreferrer" target="_blank">
                      Open Compare
                    </a>
                  </div>
                </div>
                <div className="case-detail-metrics">
                  <DetailChip label="mode" value={safeText(item.execution_mode)} />
                  <DetailChip label="shared prefix" value={numberish(item.shared_prefix_trace_count)} />
                  <DetailChip label="claude traces" value={numberish(item.claude_trace_count)} />
                  <DetailChip label="innercc traces" value={numberish(item.innercc_trace_count)} />
                </div>
                <div className="analysis-chip-list">
                  {(item.variant_names || []).map((variantName) => (
                    <span className="analysis-chip subtle" key={`${item.compare_id}-${variantName}`}>
                      {variantName}
                    </span>
                  ))}
                </div>
                <div className="analysis-links">
                  {item.comparison_url ? (
                    <a className="ghost-button" href={artifactViewerUrl(item.comparison_url)} rel="noreferrer" target="_blank">
                      comparison.md
                    </a>
                  ) : null}
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="empty-state">No compare runs found.</div>
        )}
      </section>
    </main>
  );
}
