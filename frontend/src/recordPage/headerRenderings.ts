// How the header's one flat list becomes its renderings (tickets 65 and 77),
// and what happens when it asks for more top-level controls than fit (66).
import { Surface, type ResolvedItem } from "./surface";
import type { HeaderAction, Position } from "./types";

/** The displays that hold other items, as against `button` and the default. */
export type ContainerDisplay = "dropdown" | "section";

/**
 * How many containers may be stacked (ticket 76 §3). Ours to choose, but half
 * of it is forced: `MenuGroupOption.options` is `MenuOption[]` and `MenuOption`
 * excludes `MenuGroupOption`, so a section inside a band cannot keep its title
 * at any depth. A *submenu* could nest further — `MenuSubmenuOption.submenu` is
 * `MenuOptions`, which does admit groups — and is capped anyway, so `order` and
 * the overflow projection stay unambiguous.
 */
export const MAX_CONTAINER_DEPTH = 2;

/**
 * One row of a rendered list: an action, or a container holding more rows.
 *
 * The *authored* vocabulary stays flat — every item is still addressable by its
 * one name — and the nesting appears only here, where the rendering is decided
 * (ticket 77 §3).
 */
export interface HeaderNode {
  item: HeaderAction;
  /** Set when this row holds others; absent on a plain action row. */
  container?: ContainerDisplay;
  /**
   * Set when this container could not render where it was declared. It is then
   * a band of the `⋯` menu and never a top-level control, so a `group` cycle
   * cannot win a slot in the header row (ticket 77 §3).
   */
  clamped?: boolean;
  members: HeaderNode[];
}

/** A control the host draws in the header itself, left of `⋯ │ Save`. */
export type HeaderControl =
  | { kind: "button"; item: HeaderAction }
  | { kind: "dropdown"; item: HeaderAction; members: HeaderNode[] };

/**
 * One band of the `⋯` menu. A band shows a heading iff its container was
 * declared — a `section` the author wrote, or a dropdown that did not fit and
 * collapsed whole (ticket 77 §7, restating 66 §4).
 */
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
 * Project the resolved items into the header's controls and the `⋯` menu's
 * bands, given how many top-level controls the host has room for.
 *
 * Takes the resolved list rather than the visible one because a **hidden
 * container takes its members with it**, however deep: it is a floor above them,
 * as a hidden `panelSection` is above its fields, and `hide('telephony')` is how
 * a script removes the whole control (tickets 66 §5 and 77).
 *
 * Overflow is host-side and unobservable: a script cannot read back that its
 * button was demoted, so nothing here writes to the surface.
 */
export function projectHeaderActions(
  resolved: ResolvedItem<HeaderAction>[],
  budget: number
): HeaderProjection {
  if (import.meta.env.DEV) for (const entry of resolved) warnItem(entry.item);
  const items = surviving(resolved);
  const containers = containersOf(items);
  const tree = prune(build(items, containers));
  // An empty dropdown is a button that opens nothing, so it is dropped before
  // the budget applies and its slot passes to the next control in order.
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

/**
 * The items a hidden container has not taken with it.
 *
 * Only a *container* is a floor: a `group` naming a plain item names no
 * container at all, which is the undeclared branch, so that item's own
 * visibility says nothing about the band.
 */
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
 * Where a container actually renders. One that nests too deep is **clamped to
 * the deepest level it can reach, never ignored**: ignoring its `group` would
 * promote it to a top-level control, where it would eat a budget slot and
 * compete with the record's title (ticket 77 §3). A cycle reaches no level at
 * all, so it lands in `⋯` as a band of its own — reachable, titled, and costing
 * nothing.
 */
function placeContainer(
  item: HeaderAction,
  containers: Map<string, HeaderAction>
) {
  const depth = depthOf(item.name, containers);
  if (depth <= MAX_CONTAINER_DEPTH) {
    const group = declaredGroup(item, containers);
    // Legal depth, but a band cannot hold a band, so this one renders with its
    // title dropped. Said out loud because it is the author's own declaration
    // losing, not the viewport taking it (which is demotion, and silent).
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

/**
 * The one rule, with its default: `group: 'x'` puts an item inside the item
 * named `x`; an undeclared `x` synthesises an anonymous, untitled container,
 * which is the adjacency band a script has always got (ticket 77 §2).
 */
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
  // A member joins its container wherever the container sits: a container is
  // placed by its own item, never by its first member (ticket 65).
  items.forEach((item, index) => {
    const node = nodes.get(item.name)!;
    const parent = parents[index];
    if (parent) nodes.get(parent)!.members.push(node);
    else top.push(node);
  });
  return top;
}

/**
 * Drop every dropdown left with nothing in it, at any depth: it is a trigger
 * that opens nothing, which is 66 §5's rule about a top-level control applied
 * where clamping actually produces the case — a container whose only member was
 * lifted out from under it. A *section* needs no such rule; an empty group is
 * dropped by frappe-ui's own normalization.
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

// A demoted control keeps a band of its own, ahead of the built-ins and in
// top-level order, with no signal that it wanted to be a button (ticket 66 §4).
// Banding by its own name, not by its `group`, is what keeps a demoted button
// from reading as a member of a dropdown that was demoted beside it.
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

/**
 * A band's rows. A submenu survives here — `MenuSubmenuOption` is a legal
 * `MenuOption` — but a section cannot keep its title inside a band, so it
 * flattens and its members are spliced in where it sat (ticket 77 §4). That is
 * demotion being lossy, silent and unobservable, as 66 already had it.
 */
function bandRows(nodes: HeaderNode[]): HeaderNode[] {
  return nodes.flatMap((node) =>
    node.container === "section" ? bandRows(node.members) : [node]
  );
}

// Bands are derived from the one flat list by adjacency, except where an author
// declared a container: a top-level `section` titles a band and consumes no
// budget slot, since it is not a control (ticket 77 §2).
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
 * Which list an item is ordered within, as a comparable key. Read off the
 * **declared** `display` and never off the effective one, so nothing computed
 * from it can become width-dependent (ticket 66 §5): a demoted control is still
 * `row` here, because demotion is the host's answer to a width, not the
 * author's to a question.
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
 * The header's surface, which is an ordinary `Surface` plus one warning: an
 * anchor naming an item in a different rendering still splices where it always
 * did, and says so (ticket 65).
 *
 * The check runs over the *resolved* list rather than at call time, because a
 * member can be added before the container that decides its rendering.
 */
export class HeaderActionsSurface extends Surface<HeaderAction> {
  private claims: AnchorClaim[] = [];
  private said = new Set<string>();

  // One claim per **block**, not per item: a block splices as a unit, so only
  // its head is anchored where the caller asked. Claiming the rest would
  // report an anchor they were never given.
  add(item: HeaderAction | HeaderAction[], position?: Position) {
    const block = Array.isArray(item) ? item : [item];
    if (block.length) this.claim("add", block[0].name, position);
    super.add(item, position);
  }

  move(name: string, position: Position) {
    this.claim("move", name, position);
    super.move(name, position);
  }

  // Claims are staged with the ops they belong to: a replay rebuilds the list
  // from built-ins, so the claims that produced the old one go with it.
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
      // Anchoring a member at its own container is how an author says "first
      // in this dropdown", and it does exactly that. The two sit in different
      // lists, but one of them *is* the other's list.
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

// Said once per message, for the same reason the anchor warning is: a
// projection runs on every render, and a warning that repeats with the frame
// rate is a warning nobody reads.
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

// What an item declared about itself, checked before anything is placed —
// including for a hidden item, since these are complaints about the
// declaration and not about the rendering. `display` type-checks whatever it is
// given (`SurfaceItem` carries an index signature), so an unknown value is
// silently the default: 65's trap a second time, and worth a word.
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
  // `group` decides *where* an item goes and `display` only decides what it
  // looks like once it is there, so a button inside a container is an ordinary
  // row. Two declarations that disagree should not be settled in silence.
  if (display === "button" && item.group)
    warnOnce(
      `headerActions: '${item.name}' is a button inside '${item.group}', and a ` +
        `container holds rows, not buttons — if it should stand on its own, drop its \`group\`.`
    );
}
