// What the header's finder lists for a query: the selected field's properties, the fields, the
// Settings rows. Each group holds at most LIMIT items.
import { __ } from "@/i18n";
import type { DesignCanvas } from "./designCanvas";
import { LAYOUT_BREAKS } from "./fieldRules";
import { activePanel, revealProperty } from "./panelIndex";
import { SECTIONS, settingRows, type DangerScope } from "./settingsRows";

export interface FinderItem {
  key: string;
  label: string;
  suffix: string;
  pick: () => void;
}

export interface FinderGroup {
  label: string;
  items: FinderItem[];
}

export interface FinderHost {
  canvas: DesignCanvas | null;
  /** The Danger zone's scope, which decides whether its rows show. */
  scope: DangerScope | null;
  /** Whether the panel of the selected field is on screen. */
  panelShown: boolean;
  find: (fieldname: string) => void;
  findSetting: (key: string) => void;
}

const LIMIT = 6;

export function finderGroups(host: FinderHost, query: string): FinderGroup[] {
  const typed = query.trim().toLowerCase();
  return [
    { label: propertiesLabel(host.canvas), items: propertyItems(host, typed) },
    { label: __("Fields"), items: fieldItems(host, typed) },
    { label: __("Settings"), items: settingItems(host, typed) },
  ].filter((group) => group.items.length);
}

function propertiesLabel(canvas: DesignCanvas | null) {
  const field = canvas?.selectedField.value;
  return field ? __("Properties of {0}", [field.label || field.fieldname]) : "";
}

function propertyItems(host: FinderHost, typed: string): FinderItem[] {
  const panel = activePanel.value;
  if (!host.panelShown || !host.canvas?.selectedField.value || !panel)
    return [];
  return [...panel.rows.entries()]
    .filter(([, row]) => matches(row.text, typed))
    .slice(0, LIMIT)
    .map(([id, row]) => ({
      key: `property-${id}`,
      label: row.label,
      suffix: panel.groups.get(row.group)?.label ?? "",
      pick: () => void revealProperty(panel, row),
    }));
}

function fieldItems({ canvas, find }: FinderHost, typed: string): FinderItem[] {
  if (!canvas) return [];
  const sections = sectionLabels(canvas);
  const off = new Set(
    canvas.allOffLayout.value.map(({ field }) => field.fieldname),
  );
  return canvas.working.value.fields
    .filter((field) => !LAYOUT_BREAKS.includes(field.fieldtype))
    .map((field) => ({
      key: `field-${field.fieldname}`,
      label: field.label
        ? __(field.label, [], canvas.state.doctype)
        : field.fieldname,
      suffix: off.has(field.fieldname)
        ? __("Not on this layout")
        : (sections.get(field.fieldname) ?? ""),
      text: `${field.label ?? ""} ${field.fieldname}`,
      pick: () => find(field.fieldname),
    }))
    .filter((item) => matches(`${item.text} ${item.suffix}`, typed))
    .slice(0, LIMIT);
}

function settingItems(
  { canvas, scope, findSetting }: FinderHost,
  typed: string,
): FinderItem[] {
  if (!canvas) return [];
  const sections = new Map(SECTIONS.map((section) => [section.key, section]));
  return settingRows(canvas.working.value.settings, scope)
    .filter((row) =>
      matches(
        [__(row.label), row.label, row.help, row.keywords ?? ""].join(" "),
        typed,
      ),
    )
    .slice(0, LIMIT)
    .map((row) => ({
      key: `setting-${row.key}`,
      label: __(row.label),
      suffix: __(sections.get(row.section)!.label),
      pick: () => findSetting(row.key),
    }));
}

/** Each field's section label, by fieldname. */
function sectionLabels(canvas: DesignCanvas) {
  const labels = new Map<string, string>();
  for (const tab of canvas.tabs.value) {
    for (const section of tab.sections) {
      for (const column of section.columns) {
        for (const entry of column.fields)
          if (typeof entry === "string") labels.set(entry, section.label ?? "");
      }
    }
  }
  return labels;
}

function matches(text: string, typed: string) {
  return text.toLowerCase().includes(typed);
}
