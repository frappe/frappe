// Reads a layer's concepts, the five flows and the ways to change the desk from ARCHITECTURE.md.

export function conceptsOf(markdown, layer) {
  const lines = markdown.split("\n");
  const heading = lines.findIndex(
    (l) => l.startsWith("### ") && slug(l.slice(4)) === layer.section
  );
  if (heading < 0) return [];
  const rows = [];
  let underLabel = !layer.table;
  let header = null;
  for (const line of lines.slice(heading + 1)) {
    if (line.startsWith("## ") || line.startsWith("### ")) break;
    // "Outside the layers" holds two tables, each under a bold label.
    if (layer.table && line.startsWith("**")) underLabel = line === layer.table;
    const cells = tableCells(line);
    if (!cells) header = null;
    else if (!header) header = cells[0];
    // A layer can hold other tables, such as the import list; only concept rows count.
    else if (
      underLabel &&
      header === "Concept" &&
      cells.length === 2 &&
      !/^-+$/.test(cells[0])
    ) {
      rows.push({ name: cells[0], what: cells[1] });
    }
  }
  return rows;
}

export function flowsOf(markdown) {
  const lines = markdown.split("\n");
  const start = lines.indexOf("## The five flows");
  if (start < 0) return [];
  const end = lines.findIndex((l, i) => i > start && l.startsWith("## "));
  const flows = [];
  for (const line of lines.slice(start + 1, end < 0 ? undefined : end)) {
    if (line.startsWith("### "))
      flows.push({ title: line.slice(4), steps: [], budget: "" });
    const flow = flows.at(-1);
    if (flow) readFlowLine(flow, line);
  }
  return flows.map(({ inBudget, ...flow }) => flow);
}

export function extensionsOf(markdown) {
  const lines = markdown.split("\n");
  const start = lines.indexOf("## Ways to change the desk");
  if (start < 0) return [];
  const rows = [];
  for (const line of lines.slice(start + 1)) {
    if (line.startsWith("## ")) break;
    const cells = tableCells(line);
    if (cells?.length !== 7 || cells[0] === "Way" || /^-+$/.test(cells[0]))
      continue;
    const [name, who, layer, how, changes, pair, pairNote] = cells;
    rows.push({
      name,
      tier: who.toLowerCase(),
      layer,
      how,
      changes,
      pair,
      pairNote,
    });
  }
  return rows;
}

function readFlowLine(flow, line) {
  const cells = tableCells(line);
  if (cells?.length === 5 && /^\d+[a-z]?$/.test(cells[0])) {
    const [n, step, layerText, check, cache] = cells;
    const layers = (layerText.match(/\d|main\.ts|index\.html/g) || []).map(
      (l) => (l === "main.ts" ? "main" : l)
    );
    flow.steps.push({ n, step, layers, layerText, check, cache });
  }
  if (line.startsWith("**Budget:**")) flow.inBudget = true;
  if (!line.trim()) flow.inBudget = false;
  if (flow.inBudget)
    flow.budget = `${flow.budget} ${line.replace("**Budget:**", "")}`.trim();
}

function tableCells(line) {
  if (!line.startsWith("|")) return null;
  return line
    .split("|")
    .slice(1, -1)
    .map((c) => c.trim());
}

// GitHub's heading anchors, for the headings ARCHITECTURE.md uses.
export function slug(text) {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9 -]/g, "")
    .trim()
    .replace(/ /g, "-");
}
