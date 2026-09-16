// The header's projected rows, spelled in frappe-ui's `Menu` vocabulary.
import type { HeaderItem, HeaderNode } from "@/recordPage";

type Run = (item: HeaderItem) => void;

/** Rows for a list that may hold groups: a dropdown's content, or the `⋯` menu's bands. */
export function menuContent(nodes: HeaderNode[], run: Run): any[] {
  return nodes.map((node) => {
    // `MenuGroupOption` has no icon slot, so a section's icon renders nowhere.
    if (node.container === "section")
      return { group: node.item.label, options: bandRows(node.members, run) };
    return row(node, run);
  });
}

/** Rows for the inside of a band, which may not hold groups; the engine flattened them. */
export function bandRows(nodes: HeaderNode[], run: Run): any[] {
  return nodes.map((node) => row(node, run));
}

// The item's own keys go on last: `props` was filtered to the option's declared keys, not the engine's.
function row(node: HeaderNode, run: Run) {
  const base = { ...node.props, label: node.item.label, icon: node.item.icon };
  // A submenu trigger can never also be an action, which is why a container's `run` warns.
  if (node.container === "dropdown") return { ...base, submenu: menuContent(node.members, run) };
  // `run` wins over `href`, as the item type promises.
  if (!node.item.run && node.item.href) return { ...base, route: node.item.href };
  // A `route` in props is the link when the item has neither; the engine has dropped it otherwise.
  if (!node.item.run && base.route) return base;
  return { ...base, onClick: () => run(node.item) };
}
