// Builds the desk import graph between folders, with the folder groups that import each other in a cycle.

import path from "node:path";
import { Sources } from "./sources.mjs";

// These folders hold unrelated modules side by side, so each file in them is its own node.
const FLAT_FOLDERS = ["frontend/src", "ui/src", "frappe/shell"];

export function buildGraph(root) {
  return new FolderGraph(new Sources(root)).build();
}

class FolderGraph {
  constructor(sources) {
    this.sources = sources;
    this.nodes = new Map();
    this.edges = new Map();
  }

  build() {
    const jsFiles = this.sources.jsFiles();
    const pyFiles = this.sources.pyFiles();
    for (const [file, info] of jsFiles) this.addFile(file, info.lines);
    for (const [file, info] of pyFiles) this.addFile(file, info.lines);
    for (const [file, info] of jsFiles) this.addJsEdges(file, info);
    for (const [file, info] of pyFiles) this.addPyEdges(file, info);
    this.addShellCallerEdges();

    const edges = [...this.edges.values()].sort((a, b) => b.count - a.count);
    return { nodes: this.nodeList(), edges, folderCycles: folderCycles(edges) };
  }

  addJsEdges(file, info) {
    const from = nodeOf(file);
    for (const imp of info.imports) {
      if (imp.external) this.countExternal(from, imp.external);
      else if (imp.target) {
        this.addEdge(
          from,
          nodeOf(imp.target),
          imp.kind,
          [file, imp.target, imp.line],
          imp
        );
      }
    }
    for (const call of info.apiCalls) {
      const target = this.sources.resolvePythonMethod(call.method);
      if (!target) continue;
      this.ensureServerFile(target);
      this.addEdge(from, nodeOf(target), "api", [file, target, call.line]);
    }
  }

  addPyEdges(file, info) {
    for (const { target, line } of info.imports) {
      this.ensureServerFile(target);
      this.addEdge(nodeOf(file), nodeOf(target), "import", [
        file,
        target,
        line,
      ]);
    }
  }

  addShellCallerEdges() {
    for (const ref of this.sources.shellCallers()) {
      this.ensureServerFile(ref.from);
      this.addEdge(nodeOf(ref.from), nodeOf(ref.to), ref.kind, [
        ref.from,
        ref.to,
        ref.line,
      ]);
    }
  }

  addFile(file, lines) {
    const id = nodeOf(file);
    if (!this.nodes.has(id))
      this.nodes.set(id, { id, lines: 0, fileList: [], externals: {} });
    const node = this.nodes.get(id);
    if (node.fileList.some((f) => f.path === file)) return;
    node.fileList.push({ path: file, lines });
    node.lines += lines;
  }

  // Python files outside frappe/shell join the graph only when something reaches them.
  ensureServerFile(file) {
    const lines = this.sources.lineCount(file);
    if (lines !== null) this.addFile(file, lines);
  }

  countExternal(nodeId, pkg) {
    const externals = this.nodes.get(nodeId).externals;
    externals[pkg] = (externals[pkg] || 0) + 1;
  }

  // An import inside one folder stays: the layer file can split a folder across two layers.
  addEdge(from, to, kind, pair, { typeOnly = false, dynamic = false } = {}) {
    const key = `${from}|${to}|${kind}`;
    if (!this.edges.has(key)) {
      this.edges.set(key, {
        from,
        to,
        kind,
        count: 0,
        typeOnly: 0,
        dynamic: 0,
        pairs: [],
      });
    }
    const edge = this.edges.get(key);
    edge.count += 1;
    if (typeOnly) edge.typeOnly += 1;
    if (dynamic) edge.dynamic += 1;
    if (!edge.pairs.some(([a, b]) => a === pair[0] && b === pair[1]))
      edge.pairs.push(pair);
  }

  nodeList() {
    return [...this.nodes.values()]
      .map(({ id, lines, fileList, externals }) => {
        return { id, files: fileList.length, lines, fileList, externals };
      })
      .sort((a, b) => a.id.localeCompare(b.id));
  }
}

function nodeOf(file) {
  const dir = path.dirname(file);
  return FLAT_FOLDERS.includes(dir) ? file : dir;
}

function folderCycles(edges) {
  const imports = edges.filter((e) => e.kind === "import");
  return stronglyConnected(adjacency(imports)).filter(
    (group) => group.length > 1
  );
}

function adjacency(edges) {
  const adj = new Map();
  for (const { from, to } of edges) {
    if (from === to) continue;
    if (!adj.has(from)) adj.set(from, new Set());
    if (!adj.has(to)) adj.set(to, new Set());
    adj.get(from).add(to);
  }
  return adj;
}

// Tarjan's algorithm.
function stronglyConnected(adj) {
  let index = 0;
  const stack = [];
  const meta = new Map();
  const groups = [];
  const visit = (v) => {
    meta.set(v, { index, low: index, onStack: true });
    index += 1;
    stack.push(v);
    for (const w of adj.get(v) || []) {
      if (!meta.has(w)) {
        visit(w);
        meta.get(v).low = Math.min(meta.get(v).low, meta.get(w).low);
      } else if (meta.get(w).onStack) {
        meta.get(v).low = Math.min(meta.get(v).low, meta.get(w).index);
      }
    }
    if (meta.get(v).low === meta.get(v).index)
      groups.push(popGroup(stack, meta, v));
  };
  for (const v of adj.keys()) if (!meta.has(v)) visit(v);
  return groups;
}

function popGroup(stack, meta, root) {
  const group = [];
  let w;
  do {
    w = stack.pop();
    meta.get(w).onStack = false;
    group.push(w);
  } while (w !== root);
  return group.sort();
}
