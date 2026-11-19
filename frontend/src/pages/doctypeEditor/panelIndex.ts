// The field panel's rows by group, for the header finder: each PanelRow registers its label under
// its PanelSection, and a pick opens the group, scrolls to the row and flashes it.
import {
  inject,
  markRaw,
  nextTick,
  onBeforeUnmount,
  provide,
  reactive,
  shallowRef,
  watchEffect,
  type InjectionKey,
  type Ref,
} from "vue";

export interface PanelIndex {
  groups: Map<number, { label: string; open: Ref<boolean> }>;
  rows: Map<number, PanelIndexRow>;
}

export interface PanelIndexRow {
  group: number;
  label: string;
  text: string;
  el: () => HTMLElement | null;
}

const PanelIndexKey: InjectionKey<PanelIndex> = Symbol("PanelIndex");
const PanelGroupKey: InjectionKey<number> = Symbol("PanelGroup");

/** The panel on screen; `null` while none registers rows. */
export const activePanel = shallowRef<PanelIndex | null>(null);

/** Words that find a property its label does not name. */
const KEYWORDS: Record<string, string> = {
  Label: "name title",
  Type: "fieldtype",
  Required: "mandatory reqd",
  Default: "initial value",
  "Help text": "description",
  "Links to": "options doctype link",
  Filters: "link_filters filter query",
  Hidden: "hide",
  "Read only": "readonly",
  "In list view": "column",
  "Search index": "index",
  "Perm level": "permission level permlevel",
};

export function providePanelIndex() {
  const index = reactive({ groups: new Map(), rows: new Map() }) as PanelIndex;
  provide(PanelIndexKey, index);
  activePanel.value = index;
  onBeforeUnmount(
    () => activePanel.value === index && (activePanel.value = null),
  );
}

let nextGroup = 1;

/** For a PanelSection: the group its rows register under. */
export function usePanelGroup(label: () => string, open: Ref<boolean>) {
  const index = inject(PanelIndexKey, null);
  const group = nextGroup++;
  provide(PanelGroupKey, group);
  if (!index) return;
  // Raw: the reactive map would unwrap `open` to its boolean.
  watchEffect(() =>
    index.groups.set(group, markRaw({ label: label(), open })),
  );
  onBeforeUnmount(() => index.groups.delete(group));
}

let nextRow = 1;

/** For a PanelRow: registers its label, and its keywords. */
export function usePanelRow(label: () => string, el: () => HTMLElement | null) {
  const index = inject(PanelIndexKey, null);
  if (!index) return;
  const group = inject(PanelGroupKey, 0);
  const id = nextRow++;
  watchEffect(() => {
    const name = label();
    if (name)
      index.rows.set(id, {
        group,
        label: name,
        text: `${name} ${KEYWORDS[name] ?? ""}`,
        el,
      });
    else index.rows.delete(id);
  });
  onBeforeUnmount(() => index.rows.delete(id));
}

export async function revealProperty(index: PanelIndex, row: PanelIndexRow) {
  const group = index.groups.get(row.group);
  if (group) group.open.value = true;
  await nextTick();
  flash(row.el());
}

/** A brief gray background on the row the finder took you to. */
export function flash(el: HTMLElement | null) {
  if (!el) return;
  el.scrollIntoView({ block: "center", behavior: "smooth" });
  el.classList.add(
    "rounded-4",
    "bg-surface-gray-3",
    "transition-colors",
    "duration-300",
  );
  setTimeout(() => el.classList.remove("bg-surface-gray-3"), 1200);
}
