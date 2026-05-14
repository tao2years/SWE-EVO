import {
  buildCompareRunDetail,
  buildCompareVariantTraceDetail,
} from "@/lib/dashboard-data";

function safeText(value) {
  return value === null || value === undefined || value === "" ? "n/a" : String(value);
}

function numberish(value) {
  return typeof value === "number" ? value.toLocaleString() : "n/a";
}

function percent(value) {
  return typeof value === "number" ? `${(value * 100).toFixed(1)}%` : "n/a";
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

function ArtifactLinks({ artifacts }) {
  const entries = Object.entries(artifacts || {}).filter(([, url]) => Boolean(url));
  if (!entries.length) {
    return <div className="empty-state">No artifacts.</div>;
  }
  return (
    <div className="artifact-links">
      {entries.map(([name, url]) => (
        <a href={artifactViewerUrl(url)} key={name} rel="noreferrer" target="_blank">
          {name}
        </a>
      ))}
    </div>
  );
}

function renderToolSummary(item) {
  const bits = [item.tool_name || "tool"];
  if (item.summary) {
    bits.push(item.summary);
  } else if (item.tool_summary) {
    bits.push(item.tool_summary);
  }
  return bits.join(" · ");
}

function TraceTurnDetails({ turn }) {
  return (
    <details className="compare-trace-turn">
      <summary>
        <span>turn {turn.index}</span>
        <span>{numberish(turn.assistant?.usage?.input_tokens)} in</span>
        <span>{numberish(turn.assistant?.usage?.cache_read_input_tokens)} cache</span>
        <span>{numberish(turn.assistant?.usage?.output_tokens)} out</span>
        <span>{safeText(turn.assistant?.stop_reason)}</span>
      </summary>
      <div className="compare-trace-turn-body">
        {(turn.request_messages || []).map((message, index) => {
          if (message.kind === "user_text") {
            return (
              <section className="trace-message trace-message-user" key={`user-${turn.index}-${index}`}>
                <div className="trace-label">User</div>
                <pre className="trace-text">{message.text}</pre>
              </section>
            );
          }
          if (message.kind === "tool_results") {
            return (
              <section className="trace-message trace-message-tool" key={`result-${turn.index}-${index}`}>
                <div className="trace-label">Tool Results</div>
                <div className="trace-list">
                  {(message.results || []).map((item, resultIndex) => (
                    <div className="tool-payload" key={`${item.tool_use_id || resultIndex}-tool-result`}>
                      <div className="tool-header">
                        <span className="tool-kind">result</span>
                        <strong>{renderToolSummary(item)}</strong>
                        {item.is_error ? <span className="bool-false">error</span> : null}
                      </div>
                      <pre className="tool-content">{item.content || "(empty)"}</pre>
                    </div>
                  ))}
                </div>
              </section>
            );
          }
          return null;
        })}
        <section className="trace-message trace-message-assistant">
          <div className="trace-label">Assistant</div>
          {turn.assistant?.text ? <pre className="trace-text">{turn.assistant.text}</pre> : null}
          {turn.assistant?.tool_calls?.length ? (
            <div className="trace-list">
              {turn.assistant.tool_calls.map((item, index) => (
                <div className="tool-payload" key={`${item.tool_use_id || index}-tool-call`}>
                  <div className="tool-header">
                    <span className="tool-kind">call</span>
                    <strong>{renderToolSummary(item)}</strong>
                  </div>
                  {item.input_json ? <pre className="tool-content">{item.input_json}</pre> : null}
                </div>
              ))}
            </div>
          ) : null}
          {!turn.assistant?.text && !turn.assistant?.tool_calls?.length ? (
            <div className="trace-empty">No assistant body captured.</div>
          ) : null}
        </section>
      </div>
    </details>
  );
}

function CompareDiffTable({ leftTrace, rightTrace, leftLabel, rightLabel }) {
  const length = Math.max(leftTrace?.turns?.length || 0, rightTrace?.turns?.length || 0);
  const rows = [];
  for (let index = 0; index < length; index += 1) {
    rows.push({
      left: leftTrace?.turns?.[index] || null,
      right: rightTrace?.turns?.[index] || null,
      turn: index + 1,
    });
  }

  return (
    <div className="table-wrap compare-diff-wrap">
      <table className="case-table compare-diff-table">
        <thead>
          <tr>
            <th>turn</th>
            <th>{leftLabel} input</th>
            <th>{rightLabel} input</th>
            <th>{leftLabel} cache_read</th>
            <th>{rightLabel} cache_read</th>
            <th>{leftLabel} tools</th>
            <th>{rightLabel} tools</th>
            <th>{leftLabel} stop</th>
            <th>{rightLabel} stop</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={`compare-turn-${row.turn}`}>
              <td>{row.turn}</td>
              <td>{numberish(row.left?.assistant?.usage?.input_tokens)}</td>
              <td>{numberish(row.right?.assistant?.usage?.input_tokens)}</td>
              <td>{numberish(row.left?.assistant?.usage?.cache_read_input_tokens)}</td>
              <td>{numberish(row.right?.assistant?.usage?.cache_read_input_tokens)}</td>
              <td>{numberish(row.left?.assistant?.tool_calls?.length || 0)}</td>
              <td>{numberish(row.right?.assistant?.tool_calls?.length || 0)}</td>
              <td>{safeText(row.left?.assistant?.stop_reason)}</td>
              <td>{safeText(row.right?.assistant?.stop_reason)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default async function CompareRunPage({ compareId }) {
  const detail = await buildCompareRunDetail(compareId);
  if (!detail) {
    return (
      <main className="artifact-shell">
        <section className="artifact-hero">
          <div>
            <p className="eyebrow">Compare Run</p>
            <h1>Compare run not found</h1>
            <p className="hero-copy">The requested compare run directory does not exist.</p>
          </div>
        </section>
      </main>
    );
  }

  const traces = {};
  for (const variant of detail.variants || []) {
    traces[variant.variant_name] = await buildCompareVariantTraceDetail(compareId, variant.variant_name);
  }
  const [leftVariant, rightVariant] = detail.variants || [];
  const leftTrace = leftVariant ? traces[leftVariant.variant_name] : null;
  const rightTrace = rightVariant ? traces[rightVariant.variant_name] : null;

  return (
    <main className="artifact-shell compare-run-shell">
      <section className="artifact-hero">
        <div>
          <p className="eyebrow">Compare Run</p>
          <h1>{detail.compare_id}</h1>
          <p className="hero-copy artifact-path">
            {safeText(detail.instance?.instance_id || detail.metadata?.instance_id)} · {safeText(detail.metadata?.repo)}
          </p>
        </div>
        <div className="artifact-meta">
          <DetailChip label="mode" value={safeText(detail.metadata?.execution_mode || "serial")} />
          <DetailChip label="model" value={safeText(detail.metadata?.model)} />
          <DetailChip label="shared prefix" value={numberish(detail.comparison?.shared_prefix?.shared_prefix_trace_count)} />
          <DetailChip label="selected by" value={safeText(detail.comparison?.selected_by?.instance_id)} />
        </div>
      </section>

      <section className="panel compare-panel">
        <div className="artifact-json-header">
          <div>
            <h2>Compare Summary</h2>
            <p className="panel-note">This view is built from `custom_cli_case/compare_runs/*` artifacts.</p>
          </div>
        </div>
        <div className="case-detail-metrics">
          <DetailChip label="historical claude hit" value={percent(detail.comparison?.selected_by?.claude_cache_hit_rate)} />
          <DetailChip label="historical innercc hit" value={percent(detail.comparison?.selected_by?.innercc_cache_hit_rate)} />
          <DetailChip label="historical gap" value={percent(detail.comparison?.selected_by?.gap)} />
          <DetailChip label="live claude traces" value={numberish(detail.comparison?.claude_code?.trace_count)} />
          <DetailChip label="live innercc traces" value={numberish(detail.comparison?.innercc_0509_context?.trace_count)} />
        </div>
        <ArtifactLinks artifacts={detail.artifacts} />
      </section>

      <section className="panel compare-panel">
        <div className="artifact-json-header">
          <div>
            <h2>Variant Summaries</h2>
            <p className="panel-note">Each variant keeps its own `cli_result`, patch, and trace artifacts.</p>
          </div>
        </div>
        <div className="compare-variant-grid">
          {(detail.variants || []).map((variant) => (
            <article className="analysis-doc" key={variant.variant_name}>
              <div className="analysis-doc-top">
                <div>
                  <div className="analysis-doc-id">{variant.variant_name}</div>
                  <div className="analysis-doc-meta">
                    rc={safeText(variant.run_summary?.cli_returncode)} · trace {numberish(variant.trace_summary?.trace_count)}
                  </div>
                </div>
              </div>
              <div className="case-detail-metrics">
                <DetailChip label="input" value={numberish(variant.trace_summary?.total_input_tokens)} />
                <DetailChip label="cache read" value={numberish(variant.trace_summary?.total_cache_read_input_tokens)} />
                <DetailChip label="final hit" value={percent(variant.trace_summary?.final_cache_hit_rate)} />
              </div>
              <ArtifactLinks artifacts={variant.artifacts} />
            </article>
          ))}
        </div>
      </section>

      {leftVariant && rightVariant ? (
        <section className="panel compare-panel">
          <div className="artifact-json-header">
            <div>
              <h2>Trace Diff</h2>
              <p className="panel-note">Side-by-side turn comparison for the same task across two CLIs.</p>
            </div>
          </div>
          <CompareDiffTable
            leftLabel={leftVariant.variant_name}
            leftTrace={leftTrace}
            rightLabel={rightVariant.variant_name}
            rightTrace={rightTrace}
          />
        </section>
      ) : null}

      <section className="panel compare-panel">
        <div className="artifact-json-header">
          <div>
            <h2>Expanded Traces</h2>
            <p className="panel-note">Click each turn to expand its user/query/tool trace.</p>
          </div>
        </div>
        <div className="compare-trace-columns">
          {(detail.variants || []).map((variant) => {
            const trace = traces[variant.variant_name];
            return (
              <section className="compare-trace-column" key={`trace-${variant.variant_name}`}>
                <h3>{variant.variant_name}</h3>
                <div className="case-detail-metrics">
                  <DetailChip label="requests" value={numberish(trace?.trace_count)} />
                  <DetailChip label="tool calls" value={numberish(trace?.total_tool_calls)} />
                  <DetailChip label="input toks" value={numberish(trace?.total_input_tokens)} />
                  <DetailChip label="output toks" value={numberish(trace?.total_output_tokens)} />
                </div>
                {trace?.turns?.length ? (
                  <div className="trace-timeline">
                    {trace.turns.map((turn) => (
                      <TraceTurnDetails key={`${variant.variant_name}-${turn.index}`} turn={turn} />
                    ))}
                  </div>
                ) : (
                  <div className="trace-empty">No parsed trace turns for this variant.</div>
                )}
              </section>
            );
          })}
        </div>
      </section>
    </main>
  );
}
