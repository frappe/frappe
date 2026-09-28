// Places every file of the import graph in a layer from layers.json and checks each import.

export class LayerCheck {
  constructor(graph, layerFile) {
    this.layerFile = layerFile;
    this.unplaced = [];
    this.loops = graph.folderCycles;
    this.boxes = this.buildBoxes(graph.nodes);
    this.edges = this.buildEdges(graph.edges);
    this.knownBreaks = this.matchKnownBreaks();
  }

  get newBreaks() {
    return this.edges
      .filter(isBreak)
      .flatMap((e) => e.pairs.filter((p) => p.known === null));
  }

  get fixedBreaks() {
    return this.knownBreaks.filter((k) => !k.stillThere);
  }

  get passes() {
    return (
      !this.newBreaks.length &&
      !this.fixedBreaks.length &&
      !this.unplaced.length
    );
  }

  report() {
    return [
      ...this.newBreaks.map(
        (p) => `NEW BREAK  ${p.from}${p.line ? ":" + p.line : ""} -> ${p.to}`
      ),
      ...this.fixedBreaks.map(
        (k) => `FIXED      ${k.from} -> ${k.to}: remove it from knownBreaks`
      ),
      ...this.unplaced.map((f) => `NO LAYER   ${f}`),
    ];
  }

  layerOf(file) {
    let best = null;
    for (const layer of this.layerFile.layers) {
      for (const p of layer.paths) {
        if (file.startsWith(p) && (!best || p.length > best.length))
          best = { id: layer.id, length: p.length };
      }
    }
    return best?.id;
  }

  // A box is the part of one graph folder that falls in one layer: `frappe` splits because
  // bundler.py belongs to the build.
  buildBoxes(nodes) {
    const boxes = new Map();
    for (const node of nodes) {
      for (const file of node.fileList) {
        const layer = this.layerOf(file.path);
        if (!layer) {
          this.unplaced.push(file.path);
          continue;
        }
        const id = `${node.id}@${layer}`;
        if (!boxes.has(id))
          boxes.set(id, {
            id,
            folder: node.id,
            layer,
            files: [],
            lines: 0,
            externals: node.externals,
          });
        boxes.get(id).files.push(file);
        boxes.get(id).lines += file.lines;
      }
    }
    return [...boxes.values()];
  }

  buildEdges(graphEdges) {
    const edges = new Map();
    for (const edge of graphEdges) {
      for (const [from, to, line] of edge.pairs) {
        const fromBox = this.boxOf(edge.from, from);
        const toBox = this.boxOf(edge.to, to);
        if (!fromBox || !toBox || fromBox === toBox) continue;
        const id = `${fromBox.id}>${toBox.id}>${edge.kind}`;
        if (!edges.has(id)) {
          const status = this.statusOf(edge.kind, fromBox.layer, toBox.layer);
          edges.set(id, {
            id,
            from: fromBox.id,
            to: toBox.id,
            kind: edge.kind,
            status,
            pairs: [],
          });
        }
        edges.get(id).pairs.push({ from, to, line });
      }
    }
    for (const e of edges.values()) e.count = e.pairs.length;
    return [...edges.values()];
  }

  statusOf(kind, from, to) {
    if (this.layerFile.notUse[kind]) return "callback";
    if (from === to) return "inside";
    const layer = this.layerFile.layers.find((l) => l.id === from);
    return layer.mayUse.includes(to) ? "allowed" : "break";
  }

  matchKnownBreaks() {
    const known = this.layerFile.knownBreaks;
    const seen = new Set();
    for (const edge of this.edges.filter(isBreak)) {
      for (const pair of edge.pairs) {
        const i = known.findIndex(
          (k) => covers(k.from, pair.from) && covers(k.to, pair.to)
        );
        pair.known = i >= 0 ? i : null;
        if (i >= 0) seen.add(i);
      }
      edge.status = edge.pairs.every((p) => p.known !== null)
        ? "known"
        : "break";
    }
    return known.map((k, i) => ({ ...k, stillThere: seen.has(i) }));
  }

  boxOf(folder, file) {
    const layer = this.layerOf(file);
    return layer && this.boxes.find((b) => b.id === `${folder}@${layer}`);
  }
}

export function isBreak(edge) {
  return edge.status === "break" || edge.status === "known";
}

// A path ending in "/" covers its folder; any other path covers only that file.
function covers(entry, file) {
  return entry.endsWith("/") ? file.startsWith(entry) : file === entry;
}
