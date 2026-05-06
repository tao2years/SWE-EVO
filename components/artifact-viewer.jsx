"use client";

import { useState } from "react";

function formatBytes(sizeBytes) {
  if (typeof sizeBytes !== "number" || Number.isNaN(sizeBytes)) {
    return "n/a";
  }
  if (sizeBytes < 1024) return `${sizeBytes} B`;
  if (sizeBytes < 1024 * 1024) return `${(sizeBytes / 1024).toFixed(1)} KB`;
  return `${(sizeBytes / 1024 / 1024).toFixed(1)} MB`;
}

function highlightText(text, query) {
  if (!query) {
    return text;
  }
  const parts = text.split(new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi"));
  return parts.map((part, index) => (
    part.toLowerCase() === query.toLowerCase()
      ? <mark key={`${part}-${index}`}>{part}</mark>
      : <span key={`${part}-${index}`}>{part}</span>
  ));
}

function JsonPrimitive({ name, value }) {
  return (
    <div className="artifact-json-leaf">
      <span className="artifact-json-key">{name}</span>
      <span className="artifact-json-value">{JSON.stringify(value)}</span>
    </div>
  );
}

function JsonNode({ name, value, depth = 0 }) {
  if (value === null || typeof value !== "object") {
    return <JsonPrimitive name={name} value={value} />;
  }

  const entries = Array.isArray(value)
    ? value.map((item, index) => [`[${index}]`, item])
    : Object.entries(value);
  const summary = Array.isArray(value)
    ? `${name} [${value.length}]`
    : `${name} {${entries.length}}`;

  return (
    <details className="artifact-json-node" open={depth < 1}>
      <summary>{summary}</summary>
      <div className="artifact-json-children">
        {entries.map(([key, child]) => (
          <JsonNode depth={depth + 1} key={`${name}-${key}`} name={key} value={child} />
        ))}
      </div>
    </details>
  );
}

function TextView({ content }) {
  const [query, setQuery] = useState("");
  const lines = content.split("\n");
  const visibleLines = query
    ? lines
        .map((line, index) => ({ line, lineNo: index + 1 }))
        .filter(({ line }) => line.toLowerCase().includes(query.toLowerCase()))
    : lines.map((line, index) => ({ line, lineNo: index + 1 }));

  return (
    <section className="artifact-panel">
      <div className="artifact-toolbar">
        <input
          className="text-input"
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search current artifact"
          type="search"
          value={query}
        />
        <div className="toolbar-note">
          {query ? `${visibleLines.length} matching lines` : `${lines.length} total lines`}
        </div>
      </div>
      <div className="artifact-code-block">
        {visibleLines.map(({ line, lineNo }) => (
          <div className="artifact-line" key={lineNo}>
            <span className="artifact-line-no">{lineNo}</span>
            <pre className="artifact-line-text">{highlightText(line, query)}</pre>
          </div>
        ))}
      </div>
    </section>
  );
}

export default function ArtifactViewer({ artifact }) {
  if (!artifact) {
    return (
      <main className="artifact-shell">
        <section className="artifact-hero">
          <div>
            <p className="eyebrow">Artifact Viewer</p>
            <h1>Artifact Not Found</h1>
            <p className="hero-copy">The requested artifact path is missing or outside the repository root.</p>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="artifact-shell">
      <section className="artifact-hero">
        <div>
          <p className="eyebrow">Artifact Viewer</p>
          <h1>{artifact.filename}</h1>
          <p className="hero-copy artifact-path">{artifact.relativePath}</p>
        </div>
        <div className="artifact-meta">
          <span className="detail-chip"><span>type</span><strong>{artifact.contentType}</strong></span>
          <span className="detail-chip"><span>size</span><strong>{formatBytes(artifact.sizeBytes)}</strong></span>
          <a className="ghost-button artifact-raw-link" href={artifact.rawUrl} rel="noreferrer" target="_blank">
            Open Raw
          </a>
        </div>
      </section>

      {!artifact.textLike ? (
        <section className="panel artifact-panel">
          <div className="empty-state">This file type is not rendered inline. Use "Open Raw".</div>
        </section>
      ) : null}

      {artifact.textLike && artifact.tooLarge ? (
        <section className="panel artifact-panel">
          <div className="empty-state">
            This artifact is too large for inline rendering. Use "Open Raw" to inspect it directly.
          </div>
        </section>
      ) : null}

      {artifact.textLike && !artifact.tooLarge && artifact.parsedJson !== null ? (
        <section className="panel artifact-panel">
          <div className="artifact-json-header">
            <h2>Structured JSON</h2>
            <p className="panel-note">Use the disclosure arrows to fold or expand nested objects and arrays.</p>
          </div>
          <div className="artifact-json-tree">
            <JsonNode name="root" value={artifact.parsedJson} />
          </div>
        </section>
      ) : null}

      {artifact.textLike && !artifact.tooLarge && artifact.content !== null ? (
        <section className="panel artifact-panel">
          <div className="artifact-json-header">
            <h2>Searchable Text</h2>
            <p className="panel-note">Search lines in-place; matching lines stay visible while the rest are filtered out.</p>
          </div>
          <TextView content={artifact.content} />
        </section>
      ) : null}
    </main>
  );
}
