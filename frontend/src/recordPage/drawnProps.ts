// A header item's `props`, filtered to what draws the item declares. The engine owns no
// list of frappe-ui's props: the host hands the declared names in, as it hands the icon source.

/** What draws a header item, other than its own `component`: frappe-ui's `Button`, or a menu option. */
export type Drawer = "button" | "menuOption";

/** The declared prop names of each drawer, read off frappe-ui by the host. */
export type DrawnProps = Record<Drawer, readonly string[]>;

// `class` reaches a `Button` as an attribute, so it is allowed where `style` is not.
const ALSO_ON_BUTTON = ["class"];

// Spelled on the item, never in `props`: a value here would race the item's own key.
const ITEM_KEYS = ["label", "icon"];

// `run` wins and `href` is the item's own link, so a link in `props` loses to both, as `href` loses to `run`.
const LINK_KEYS = ["route", "link"];

let declared: DrawnProps | null = null;
const said = new Set<string>();
let warnedNoList = false;

/** The host's declared-prop lists per drawer; `null` keeps every key, as a surface without a vocabulary does. */
export function setDrawnProps(next: DrawnProps | null) {
  declared = next;
}

/** The props to bind on the drawer; without a host list every key is kept, as a surface without a vocabulary does. */
export function forwardedProps(
  drawer: Drawer,
  item: { name: string; props?: Record<string, any>; run?: unknown; href?: string },
  source: string,
): Record<string, any> {
  const given = item.props;
  if (!given) return {};
  const kept: Record<string, any> = {};
  for (const key of Object.keys(given)) {
    if (LINK_KEYS.includes(key) && (item.run || item.href)) continue;
    if (ITEM_KEYS.includes(key)) {
      warnOnce(source, item.name, key, `set it on the item, not in props`);
      continue;
    }
    if (!accepts(drawer, key)) {
      warnOnce(source, item.name, key, `${describe(drawer)} does not declare it`);
      continue;
    }
    kept[key] = given[key];
  }
  return kept;
}

function accepts(drawer: Drawer, key: string) {
  if (drawer === "button" && ALSO_ON_BUTTON.includes(key)) return true;
  if (!declared) {
    warnNoList();
    return true;
  }
  return declared[drawer].includes(key);
}

function describe(drawer: Drawer) {
  return drawer === "button" ? "Button" : "the menu option";
}

// Once per source, item and key: a projection runs on every render.
function warnOnce(source: string, name: string, key: string, because: string) {
  if (!import.meta.env.DEV) return;
  const once = JSON.stringify([source, name, key]);
  if (said.has(once)) return;
  said.add(once);
  console.warn(
    `[record-page] header: '${name}' from ${source} has props.${key}, which ${because} — dropped.`,
  );
}

function warnNoList() {
  if (warnedNoList) return;
  warnedNoList = true;
  console.warn("[record-page] no declared-prop list; header props are forwarded unfiltered");
}

/** Test seam: the warn-once memory is module state. */
export function resetDrawnPropsWarnings(): void {
  said.clear();
  warnedNoList = false;
}
