// Turns `page.dialog.form()` options into a `FormLayoutSchema` and reports which
// mandatory fields are still empty. Pure: the `doctype` mode's fetch is the dialog's.
import { mapField } from "@framework/ui/components/FormLayout/buildLayoutFromMeta";
import { fieldsToLayout } from "@framework/ui/components/FormLayout/fieldsToLayout";
import { resolveLayout } from "@framework/ui/components/FormLayout/resolveLayout";
import type {
  FieldNode,
  FormLayoutSchema,
  RawMetaField,
  Section,
  Tab,
} from "@framework/ui/components/FormLayout/types";
import type { FieldAccess } from "@framework/ui/composables/useDocPermissions";
// The meta path's permlevel gate and section constructor, so a dialog and a
// stored layout agree on what a reader may write and which sections open.
import { withAccess } from "./formLayoutSource/fieldAccess";
import { buildColumn, buildSection } from "./formLayoutSource/section";
import type {
  PageDialogField,
  PageDialogFormOptions,
  PageDialogSection,
  PageDialogTab,
} from "./types";

/** The layout modes, in the order the dev warning names them. */
export const LAYOUT_MODES = ["fields", "tabs", "doctype"] as const;

export type LayoutMode = (typeof LAYOUT_MODES)[number] | "none";

/** The layout mode the options ask for; the modes are exclusive and the first listed wins. */
export function layoutMode(options: PageDialogFormOptions): LayoutMode {
  return LAYOUT_MODES.find((mode) => options[mode] != null) ?? "none";
}

/** Warns about the two layout requests that render nothing. */
export function warnAmbiguousLayout(options: PageDialogFormOptions): void {
  if (!import.meta.env.DEV) return;
  const given = LAYOUT_MODES.filter((mode) => options[mode] != null);
  if (given.length > 1)
    console.warn(
      `[record-page] page.dialog.form was given ${given.join(" and ")} — the layout modes are mutually exclusive, using ${given[0]}`,
    );
  // `fieldnames` names fields *of* a doctype; alone it silently renders nothing.
  if (!given.length && options.fieldnames)
    console.warn(
      "[record-page] page.dialog.form was given fieldnames without a doctype — nothing will render",
    );
}

/** A flat field list, wrapped in one unlabelled, borderless section. */
export function layoutFromFields(fields: PageDialogField[]): FormLayoutSchema {
  return fieldsToLayout(fields.map(toFieldNode));
}

/** A hand-written `tabs > sections > columns > fields` tree. */
export function layoutFromTabs(tabs: PageDialogTab[]): FormLayoutSchema {
  return tabs.map((tab): Tab => ({
    name: tab.name,
    label: tab.label,
    dependsOn: tab.depends_on,
    sections: (tab.sections ?? []).map(toSection),
  }));
}

/** The `doctype` + `fieldnames` mode: the named fields, in order, flat, from the meta. */
// Not the `Quick Entry` layout: that is a curated subset and would drop fields silently.
export function pickMetaFields(
  fields: RawMetaField[] | undefined,
  fieldnames: string[],
  fieldAccess?: (field: RawMetaField) => FieldAccess,
): FormLayoutSchema {
  const byName = new Map(
    (fields ?? []).map((field) => [field.fieldname, field]),
  );
  return fieldsToLayout(
    fieldnames
      .map((name) => byName.get(name))
      .filter(isRawField)
      .map((field) => mapField(withAccess(field, fieldAccess), {})),
  );
}

/** Force `required` fieldnames mandatory, whatever the layout said. */
export function applyRequired(
  layout: FormLayoutSchema,
  required: string[] | undefined,
): FormLayoutSchema {
  if (!required?.length) return layout;
  const forced = new Set(required);
  return mapFields(layout, (field) =>
    forced.has(field.fieldname)
      ? { ...field, reqd: true, mandatoryDependsOn: undefined }
      : field,
  );
}

/** Seed the dialog's doc: `defaults` over every field's empty value. */
export function initialDoc(
  layout: FormLayoutSchema,
  defaults: Record<string, any> | undefined,
): Record<string, any> {
  const doc: Record<string, any> = {};
  for (const field of flatFields(layout)) doc[field.fieldname] = null;
  return { ...doc, ...(defaults ?? {}) };
}

/** The labels a submit refuses over: mandatory, visible after `depends_on`, still empty. */
export function missingRequired(
  layout: FormLayoutSchema,
  doc: Record<string, any>,
): string[] {
  const missing: string[] = [];
  for (const tab of resolveLayout(layout, doc, doc)) {
    if (tab.hidden) continue;
    for (const section of tab.sections) {
      if (section.hidden) continue;
      for (const column of section.columns)
        for (const field of column.fields)
          if (field.reqd && !field.hidden && isEmpty(doc[field.fieldname]))
            missing.push(field.label || field.fieldname);
    }
  }
  return missing;
}

/** The values a submit resolves with: every field the layout rendered. */
export function formData(
  layout: FormLayoutSchema,
  doc: Record<string, any>,
): Record<string, any> {
  const data: Record<string, any> = {};
  for (const field of flatFields(layout))
    data[field.fieldname] = doc[field.fieldname];
  return data;
}

function toSection(section: PageDialogSection): Section {
  // Listed key by key: a spread is not excess-checked, so a renamed key would
  // silently stop reaching `buildSection`.
  return buildSection(
    {
      name: section.name,
      label: section.label,
      hideLabel: section.hideLabel,
      hideBorder: section.hideBorder,
      collapsible: section.collapsible,
      opened: section.opened,
      dependsOn: section.depends_on,
    },
    (section.columns ?? []).map((column) =>
      buildColumn(column, (column.fields ?? []).map(toFieldNode)),
    ),
  );
}

// `mapField` is the meta path's reading of DocField vocabulary, so both tiers agree
// on what a field means. No child metas: a dialog field list cannot describe a grid.
function toFieldNode(field: PageDialogField): FieldNode {
  return mapField(field, {});
}

function mapFields(
  layout: FormLayoutSchema,
  transform: (field: FieldNode) => FieldNode,
): FormLayoutSchema {
  return layout.map((tab) => ({
    ...tab,
    sections: tab.sections.map((section) => ({
      ...section,
      columns: section.columns.map((column) => ({
        ...column,
        fields: column.fields.map(transform),
      })),
    })),
  }));
}

function flatFields(layout: FormLayoutSchema): FieldNode[] {
  return layout.flatMap((tab) =>
    tab.sections.flatMap((section) =>
      section.columns.flatMap((column) => column.fields),
    ),
  );
}

function isRawField(field: RawMetaField | undefined): field is RawMetaField {
  return field != null;
}

function isEmpty(value: any): boolean {
  if (Array.isArray(value)) return value.length === 0;
  return value == null || value === "";
}
