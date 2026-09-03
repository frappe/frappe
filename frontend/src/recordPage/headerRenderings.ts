// How the header's one flat list becomes its renderings, and what happens when
// it asks for more top-level controls than fit.
import { Surface, type ResolvedItem } from "./surface";
import type { HeaderAction, Position } from "./types";

/** The displays that hold other items, as against `button` and the default. */
export type ContainerDisplay = "dropdown" | "section";

/**
 * Half of this is forced: `MenuOption` excludes `MenuGroupOption`, so a section
 * inside a band cannot keep its title at any depth.
 */
export const MAX_CONTAINER_DEPTH = 2;

/** One row of a rendered list: an action, or a container holding more rows. */
export interface HeaderNode {
  item: HeaderAction;
  /** Set when this row holds others; absent on a plain action row. */
  container?: ContainerDisplay;
  /** Set when this container could not render where declared; it is then a band of `⋯`, never a control. */
  clamped?: boolean;
  members: HeaderNode[];
}

/** A control the host draws in the header itself, left of `⋯ │ Save`. */
export type HeaderControl =
  | { kind: "button"; item: HeaderAction }
  | { kind: "dropdown"; item: HeaderAction; members: HeaderNode[] };

/** One band of the `⋯` menu; it shows a heading iff its container was declared. */
export interface HeaderBand {
  group: string;
  label?: string;
  items: HeaderNode[];
}

export interface HeaderProjection {
  controls: HeaderControl[];
  bands: HeaderBand[];
}

/**
 * Projects the resolved items into the header's controls and the `⋯` menu's bands.
 * Takes the resolved list, not the visible one: a hidden container takes its members with it.
 */
export function projectHeaderActions(
  resolved: ResolvedItem<HeaderAction>[],
  budget: number
): HeaderProjection {
  if (import.meta.env.DEV) for (const entry of resolved) warnItem(entry.item);
  const items = surviving(resolved);
  const containers = containersOf(items);
  const tree = prune(build(items, containers));
  // An empty dropdown is a button that opens nothing, so it is dropped before the budget applies.
  const controls = tree
    .filter(isControl)
    .map(asControl)
    .filter((control) => control.kind === "button" || control.members.length);
  const kept = Math.max(budget, 0);
  return {
    controls: controls.slice(0, kept),
    bands: [...demotedBands(controls.slice(kept)), ...menuBands(tree)],
  };
}

function containerDisplay(item: HeaderAction): ContainerDisplay | undefined {
  if (item.display === "dropdown" || item.display === "section")
    return item.display;
  return undefined;
}

function containersOf(items: HeaderAction[]) {
  const containers = new Map<string, HeaderAction>();
  for (const item of items)
    if (containerDisplay(item)) containers.set(item.name, item);
  return containers;
}

/** The items a hidden container has not taken with it; a `group` naming a plain item is no floor. */
function surviving(resolved: ResolvedItem<HeaderAction>[]): HeaderAction[] {
  const containers = containersOf(resolved.map((entry) => entry.item));
  const hidden = new Set(
    resolved.filter((entry) => entry.hidden).map((entry) => entry.item.name)
  );
  const buried = (item: HeaderAction) => {
    const seen = new Set<string>();
    let group = item.group;
    while (group && containers.has(group) && !seen.has(group)) {
      if (hidden.has(group)) return true;
      seen.add(group);
      group = containers.get(group)!.group;
    }
    return false;
  };
  return resolved
    .filter((entry) => !hidden.has(entry.item.name) && !buried(entry.item))
    .map((entry) => entry.item);
}

/**
 * How many containers deep a container sits, counting itself. `Infinity` when
 * its `group` chain cycles, which has no depth at all.
 */
function depthOf(name: string, containers: Map<string, HeaderAction>): number {
  const seen = new Set<string>([name]);
  let depth = 1;
  let group = containers.get(name)!.group;
  while (group && containers.has(group)) {
    if (seen.has(group)) return Infinity;
    seen.add(group);
    depth += 1;
    group = containers.get(group)!.group;
  }
  return depth;
}

/**
 * Where a container renders. One nesting too deep is clamped to the deepest level
 * it can reach, never promoted to a control; a cycle lands in `⋯` as a band of its own.
 */
function placeContainer(
  item: HeaderAction,
  containers: Map<string, HeaderAction>
) {
  const depth = depthOf(item.name, containers);
  if (depth <= MAX_CONTAINER_DEPTH) {
    const group = declaredGroup(item, containers);
    // A band cannot hold a band, so this one renders with its title dropped.
    if (group && containerDisplay(item) === "section")
      if (containers.get(group)!.display === "section")
        warnOnce(
          `headerActions: the section '${item.name}' is inside the section ` +
            `'${group}', which cannot hold a titled band — its members render ` +
            `under '${group}' and its own title is dropped.`
        );
    return { group, clamped: false };
  }
  warnClamp(item, depth);
  if (depth === Infinity) return { group: undefined, clamped: true };
  let group = declaredGroup(item, containers);
  while (group && depthOf(group, containers) > 1)
    group = declaredGroup(containers.get(group)!, containers);
  return { group, clamped: true };
}

/** The container an item's `group` names, if one was declared. */
function declaredGroup(
  item: HeaderAction,
  containers: Map<string, HeaderAction>
) {
  return item.group && containers.has(item.group) ? item.group : undefined;
}

/** `group: 'x'` puts an item inside the item named `x`; an undeclared `x` synthesises an anonymous container. */
function build(items: HeaderAction[], containers: Map<string, HeaderAction>) {
  const nodes = new Map<string, HeaderNode>();
  const top: HeaderNode[] = [];
  const parents: (string | undefined)[] = [];
  for (const item of items) {
    const node: HeaderNode = {
      item,
      container: containerDisplay(item),
      members: [],
    };
    nodes.set(item.name, node);
    if (!node.container) {
      parents.push(declaredGroup(item, containers));
      continue;
    }
    const placed = placeContainer(item, containers);
    if (placed.clamped) node.clamped = true;
    parents.push(placed.group);
  }
  // A container is placed by its own item, never by its first member.
  items.forEach((item, index) => {
    const node = nodes.get(item.name)!;
    const parent = parents[index];
    if (parent) nodes.get(parent)!.members.push(node);
    else top.push(node);
  });
  return top;
}

/**
 * Drops every dropdown left empty, at any depth. A section needs no such rule:
 * frappe-ui drops an empty group itself.
 */
function prune(nodes: HeaderNode[]): HeaderNode[] {
  return nodes.flatMap((node) => {
    if (!node.container) return [node];
    node.members = prune(node.members);
    if (node.container === "dropdown" && !node.members.length) return [];
    return [node];
  });
}

/** A top-level control: a bare button, or a dropdown that renders as one. */
function isControl(node: HeaderNode) {
  if (node.clamped) return false;
  return node.item.display === "button" || node.container === "dropdown";
}

function asControl(node: HeaderNode): HeaderControl {
  return node.container === "dropdown"
    ? { kind: "dropdown", item: node.item, members: node.members }
    : { kind: "button", item: node.item };
}

// A demoted control keeps a band of its own, ahead of the built-ins. Banded by its
// own name, not its `group`, so it does not read as a member of a dropdown demoted beside it.
function demotedBands(controls: HeaderControl[]): HeaderBand[] {
  return controls.map((control) =>
    control.kind === "button"
      ? { group: control.item.name, items: [row(control.item)] }
      : {
          group: control.item.name,
          label: control.item.label,
          items: bandRows(control.members),
        }
  );
}

function row(item: HeaderAction): HeaderNode {
  return { item, members: [] };
}

/** A band's rows: a section cannot keep its title inside a band, so it flattens in place. */
function bandRows(nodes: HeaderNode[]): HeaderNode[] {
  return nodes.flatMap((node) =>
    node.container === "section" ? bandRows(node.members) : [node]
  );
}

// Bands are derived by adjacency, except where an author declared a container:
// a top-level `section` titles a band and consumes no budget slot.
function menuBands(top: HeaderNode[]): HeaderBand[] {
  const bands: HeaderBand[] = [];
  for (const node of top) {
    if (isControl(node)) continue;
    if (node.container) {
      if (node.members.length)
        bands.push({
          group: node.item.name,
          label: node.item.label,
          items: bandRows(node.members),
        });
      continue;
    }
    const group = node.item.group ?? "actions";
    const last = bands[bands.length - 1];
    if (last?.group === group && last.label === undefined)
      last.items.push(node);
    else bands.push({ group, items: [node] });
  }
  return bands;
}

/**
 * Which list an item is ordered within. Read off the declared `display`, never
 * the effective one, so nothing computed from it can become width-dependent.
 */
export function renderingOf(item: HeaderAction, items: HeaderAction[]): string {
  const containers = containersOf(items);
  const group = declaredGroup(item, containers);
  if (group) return `container:${group}`;
  if (item.display === "button" || item.display === "dropdown") return "row";
  return "menu";
}

type AnchorClaim = { verb: string; name: string; anchor: string };

/**
 * An ordinary `Surface` plus one warning: an anchor naming an item in a different
 * rendering. Checked over the resolved list, since a member can be added before its container.
 */
export class HeaderActionsSurface extends Surface<HeaderAction> {
  private claims: AnchorClaim[] = [];
  private said = new Set<string>();

  // One claim per block: a block splices as a unit, so only its head is anchored.
  add(item: HeaderAction | HeaderAction[], position?: Position) {
    const block = Array.isArray(item) ? item : [item];
    if (block.length) this.claim("add", block[0].name, position);
    super.add(item, position);
  }

  move(name: string, position: Position) {
    this.claim("move", name, position);
    super.move(name, position);
  }

  // Claims are staged with the ops they belong to; a replay rebuilds the list from built-ins.
  beginReplay() {
    this.claims = [];
    super.beginReplay();
  }

  resolve() {
    const resolved = super.resolve();
    if (import.meta.env.DEV)
      this.warnCrossRendering(resolved.map((e) => e.item));
    return resolved;
  }

  private claim(verb: string, name: string, position?: Position) {
    const anchor = position?.before ?? position?.after;
    if (anchor) this.claims.push({ verb, name, anchor });
  }

  private warnCrossRendering(items: HeaderAction[]) {
    for (const claim of this.claims) {
      const item = items.find((one) => one.name === claim.name);
      const anchor = items.find((one) => one.name === claim.anchor);
      if (!item || !anchor) continue;
      if (renderingOf(item, items) === renderingOf(anchor, items)) continue;
      // Anchoring a member at its own container means "first in this dropdown", and does that.
      if (renderingOf(item, items) === `container:${claim.anchor}`) continue;
      if (renderingOf(anchor, items) === `container:${claim.name}`) continue;
      const message =
        `[record-page] headerActions.${claim.verb}('${claim.name}'): anchor ` +
        `'${claim.anchor}' renders as ${describe(anchor, items)}, but ` +
        `'${claim.name}' renders as ${describe(
          item,
          items
        )} — position orders ` +
        `items only within one rendering.`;
      if (this.said.has(message)) continue;
      this.said.add(message);
      console.warn(message);
    }
  }
}

function describe(item: HeaderAction, items: HeaderAction[]) {
  const containers = containersOf(items);
  const group = declaredGroup(item, containers);
  if (group) {
    const container = containers.get(group)!;
    const kind = container.display === "section" ? "section" : "dropdown";
    return `an entry in the “${container.label}” ${kind}`;
  }
  if (item.display === "button") return "a top-level button";
  if (item.display === "dropdown") return `the “${item.label}” dropdown button`;
  return "an entry in the ⋯ menu";
}

// Once per message: a projection runs on every render.
const warned = new Set<string>();

function warnOnce(message: string) {
  if (!import.meta.env.DEV || warned.has(message)) return;
  warned.add(message);
  console.warn(`[record-page] ${message}`);
}

/** Test seam: the warn-once memory is module state. */
export function resetHeaderWarnings(): void {
  warned.clear();
}

function warnClamp(item: HeaderAction, depth: number) {
  const where =
    depth === Infinity
      ? "sits in a `group` cycle, which reaches no level at all"
      : `nests ${depth} containers deep, and only ${MAX_CONTAINER_DEPTH} render`;
  warnOnce(
    `headerActions: '${item.name}' ${where} — ` +
      `rendered at the deepest level it can reach.`
  );
}

// Checked before anything is placed, hidden items included. `display` type-checks
// anything (`SurfaceItem` has an index signature), so an unknown value is silently the default.
function warnItem(item: HeaderAction) {
  const display = item.display;
  if (display && !containerDisplay(item) && display !== "button")
    warnOnce(
      `headerActions: '${item.name}' has display: '${display}' — expected ` +
        `'button', 'dropdown' or 'section'; rendered as an entry in the ⋯ menu.`
    );
  if (item.run && containerDisplay(item))
    warnOnce(
      `headerActions: '${item.name}' is a ${display}, a container, so its ` +
        `\`run\` never fires; the items inside it run.`
    );
  // `group` decides where an item goes; `display` only what it looks like once there.
  if (display === "button" && item.group)
    warnOnce(
      `headerActions: '${item.name}' is a button inside '${item.group}', and a ` +
        `container holds rows, not buttons — if it should stand on its own, drop its \`group\`.`
    );
}
