import type {
  Column,
  Section,
} from "@framework/ui/components/FormLayout/types";

/** The section keys a Form Layout row and a dialog both carry, so neither grows its own default. */
export interface SectionSpec {
  name?: string;
  label?: string;
  hideLabel?: boolean;
  hideBorder?: boolean;
  collapsible?: boolean;
  /** Explicit initial state; open when unset (see `buildSection`). */
  opened?: boolean;
  dependsOn?: string;
}

/** The one `Section` constructor for the stored-layout paths; open unless `opened: false`. */
export function buildSection(spec: SectionSpec, columns: Column[]): Section {
  return {
    name: spec.name,
    label: spec.label,
    hideLabel: Boolean(spec.hideLabel),
    hideBorder: Boolean(spec.hideBorder),
    collapsible: Boolean(spec.collapsible),
    opened: spec.opened !== false,
    dependsOn: spec.dependsOn,
    columns,
  };
}

/** The matching `Column` constructor; `hideLabel` is carried, not dropped. */
export function buildColumn(
  spec: { name?: string; label?: string; hideLabel?: boolean },
  fields: Column["fields"],
): Column {
  return {
    name: spec.name,
    label: spec.label,
    hideLabel: Boolean(spec.hideLabel),
    fields,
  };
}
