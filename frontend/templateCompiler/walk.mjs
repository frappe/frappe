// Calls visit once for each node below a Babel or Vue template AST root.
export function walk(node, visit, parent = null, seen = new Set()) {
  if (seen.has(node)) return;
  seen.add(node);
  if (node.type !== undefined && visit(node, parent) === false) return;
  for (const [key, child] of Object.entries(node)) {
    if (key === "loc" || !child || typeof child !== "object") continue;
    for (const item of Array.isArray(child) ? child : [child]) {
      if (item && typeof item === "object") walk(item, visit, node, seen);
    }
  }
}
