import type { FieldMeta, FormLayoutSchema } from "./types";

/**
 * Wrap a flat list of fields into a minimal single-tab / single-section /
 * single-column `FormLayoutSchema`. Used to render one child-table row inside a
 * dialog with `FormLayout` (the row-edit action): the child columns are already
 * resolved `FieldMeta`, so there are no breaks to interpret — just a flat form.
 *
 * The tab carries no label, so `FormLayout` hides the tab strip; the section
 * carries no label/border so it renders flush, like a plain form.
 */
export function fieldsToLayout(fields: FieldMeta[]): FormLayoutSchema {
  return [
    {
      sections: [
        {
          hideLabel: true,
          hideBorder: true,
          columns: [{ fields }],
        },
      ],
    },
  ];
}
