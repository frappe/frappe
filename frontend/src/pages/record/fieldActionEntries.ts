// An app's field actions on the record itself: a `⋯` row and a quick action for each, shown while a
// field of the item's type holds a value. One value runs the act; two or more ask which.
import { acts } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import type { FieldActionItem } from "@/contributions/types";
import type { HeaderItem, QuickAction, RecordPageApi } from "@/recordPage";
import { kindOf } from "@/shell/fieldActions";

interface FieldValue {
  value: string;
  /** The labels of the fields holding it, joined. */
  fields: string;
}

const FIELD_ACTION_GROUP = "field_actions";

export function fieldActionRows(items: FieldActionItem[]): HeaderItem[] {
  return items.flatMap((item) =>
    entries(item, item.label).map((entry) => ({ ...entry, group: FIELD_ACTION_GROUP, palette: false as const }))
  );
}

export function fieldActionQuickActions(items: FieldActionItem[]): QuickAction[] {
  return items.flatMap((item) =>
    entries(item, item.quickActionLabel ?? item.label).map((entry) => ({ ...entry, palette: false as const }))
  );
}

function entries(item: FieldActionItem, label: string | undefined) {
  const name = item.act.replace(/\W/g, "_");
  const shown = acts.find(item.act);
  if (!shown) return [];
  const base = { label: label ?? shown.label ?? item.act, icon: item.icon ?? shown.icon };
  const callWith = (page: RecordPageApi, value: string) =>
    page.run(item.act, item.value ? item.value(value) : value);
  return [
    {
      ...base,
      name,
      when: (page: RecordPageApi) => hasAct(item) && valuesOf(page, item).length === 1,
      run: (page: RecordPageApi) => callWith(page, valuesOf(page, item)[0].value),
    },
    {
      ...base,
      name: `${name}_from`,
      when: (page: RecordPageApi) => hasAct(item) && valuesOf(page, item).length > 1,
      argument: {
        label: __("Choose one"),
        options: (page: RecordPageApi) =>
          valuesOf(page, item).map(({ value, fields }) => ({ value, label: value, description: fields })),
      },
      run: (page: RecordPageApi, value: string) => callWith(page, value),
    },
  ];
}

/** Read live, so a gate that opens after the first paint shows the entry then. */
const hasAct = (item: FieldActionItem) => acts.find(item.act) !== undefined;

/** The saved record's distinct non-empty values in fields of the item's type, in field order. */
function valuesOf(page: RecordPageApi, item: FieldActionItem): FieldValue[] {
  if (page.isNew) return [];
  const byValue = new Map<string, string[]>();
  for (const field of page.meta?.fields ?? []) {
    if (field.hidden || kindOf(field) !== item.fieldtype) continue;
    const value = String(page.doc?.[field.fieldname] ?? "").trim();
    if (!value || (item.when && !item.when(value))) continue;
    byValue.set(value, [...(byValue.get(value) ?? []), field.label ?? field.fieldname]);
  }
  return [...byValue].map(([value, labels]) => ({ value, fields: labels.join(", ") }));
}
