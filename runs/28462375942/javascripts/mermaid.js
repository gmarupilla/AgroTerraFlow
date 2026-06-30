// Re-run mermaid on every page navigation (handles Material instant loading).
document$.subscribe(function () {
  mermaid.initialize({ startOnLoad: false });
  mermaid.run({ querySelector: ".mermaid" });
});
