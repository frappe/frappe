// Joins the Details layout with `page.form`'s resolved list: sections reordered,
// relabelled or hidden, and a script's parts placed at their neighbour's grain.
import type {
  Column,
  ColumnPart,
  FormLayoutSchema,
  Section,
  Tab,
} from "@framework/ui/components/FormLayout/types";
import { BUILTIN } from "./surface";
import type { ResolvedItem } from "./surface";
import type { FormItem } from "./types";

type Entry = ResolvedItem<FormItem>;

/** The layout's sections as the surface's built-ins, in layout order. */
export function formItems(layout: FormLayoutSchema): FormItem[] {
  return layout.flatMap((tab) => tab.sections.map(sectionItem));
}

function sectionItem(section: Section): FormItem {
  const item: FormItem = { name: section.name ?? "" };
  if (section.label) item.label = section.label;
  return item;
}

/** The layout as the surface arranges it; `page` rides into every part's props. */
export function joinForm(
  layout: FormLayoutSchema,
  resolved: Entry[],
  page: unknown,
): FormLayoutSchema {
  if (!layout.length) return layout;
  return new FormJoin(layout, resolved, page).tabs;
}

class FormJoin {
  readonly tabs: Tab[];
  private sections = new Map<string, { tab: number; section: Section }>();
  private fields = new Map<string, { tab: number; column: Column }>();
  private byName = new Map<string, Entry>();

  constructor(
    layout: FormLayoutSchema,
    private resolved: Entry[],
    private page: unknown,
  ) {
    this.tabs = layout.map((tab, index) => this.indexTab(tab, index));
    for (const entry of resolved) this.byName.set(entry.item.name, entry);
    for (const entry of resolved) if (!entry.hidden) this.place(entry);
  }

  // Cloned down to the columns, which take the parts; the source layout is never written.
  private indexTab(tab: Tab, index: number): Tab {
    for (const section of tab.sections) {
      const columns = section.columns.map((column) => ({ ...column, parts: [] }));
      this.sections.set(section.name ?? "", { tab: index, section: { ...section, columns } });
      for (const column of columns)
        for (const field of column.fields) this.fields.set(field.fieldname, { tab: index, column });
    }
    return { ...tab, sections: [] };
  }

  private place(entry: Entry) {
    const cell = entry.source === BUILTIN ? undefined : this.fieldAnchor(entry);
    if (cell) cell.column.parts?.push(this.columnPart(entry));
    else this.tabs[this.tabOf(entry, new Set())].sections.push(this.sectionFor(entry));
  }

  // A part beside a field, or beside a part that is itself beside one, is a cell.
  private fieldAnchor(entry: Entry, seen = new Set<Entry>()) {
    seen.add(entry);
    const anchor = entry.position?.before ?? entry.position?.after;
    if (!anchor) return undefined;
    const field = this.fields.get(anchor);
    if (field) return field;
    const neighbour = this.byName.get(anchor);
    if (!neighbour || neighbour.source === BUILTIN || seen.has(neighbour)) return undefined;
    return this.fieldAnchor(neighbour, seen);
  }

  // A neighbour's tab, followed through neighbours that were moved themselves.
  private tabOf(entry: Entry, seen: Set<Entry>): number {
    seen.add(entry);
    const anchor = entry.position?.before ?? entry.position?.after;
    const field = anchor ? this.fields.get(anchor) : undefined;
    if (field) return field.tab;
    const neighbour = anchor ? this.byName.get(anchor) : undefined;
    if (neighbour && !seen.has(neighbour)) return this.tabOf(neighbour, seen);
    const own = entry.source === BUILTIN ? this.sections.get(entry.item.name)?.tab : undefined;
    return own ?? this.tabs.length - 1;
  }

  private sectionFor(entry: Entry): Section {
    const stored = this.sections.get(entry.item.name);
    if (entry.source === BUILTIN && stored)
      return { ...stored.section, label: entry.item.label ?? stored.section.label };
    const { name, label } = entry.item;
    return { name, label, collapsible: false, columns: [], part: { name, ...this.drawn(entry) } };
  }

  private columnPart(entry: Entry): ColumnPart {
    const { name, label } = entry.item;
    return { name, label, ...this.drawn(entry), ...entry.position };
  }

  private drawn(entry: Entry) {
    return { component: entry.item.component, props: { ...entry.item.props, page: this.page } };
  }
}
