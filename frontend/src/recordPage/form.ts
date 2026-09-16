// The Details form surface: the layout's sections as built-ins, a script's parts
// between or beside them, and the form's tab strip as `tabs`.
import type { RawMetaField } from "@framework/ui/components/FormLayout/types";
import { LAYOUT_BREAKS } from "./fields";
import type { FormTabsSurface } from "./formTabs";
import { Surface } from "./surface";
import { FORM_ITEM_KEYS } from "./types";
import type { FormItem, Position } from "./types";

export interface FormSurfaceHost {
  /** The doctype's fields; a layout break among them is a section's own name, not a field's. */
  fields: () => RawMetaField[] | undefined;
}

export class FormSurface extends Surface<FormItem> {
  constructor(
    private host: FormSurfaceHost,
    readonly tabs: FormTabsSurface,
  ) {
    super({ surface: "form", keys: FORM_ITEM_KEYS });
  }

  // A part takes a name of its own and a component; anything else is dropped, not drawn empty.
  add(item: FormItem | FormItem[], position?: Position) {
    const given = Array.isArray(item) ? item : [item];
    const parts = given.filter((one) => this.isNotField(one.name, "add") && this.hasComponent(one));
    if (parts.length) super.add(parts, position);
  }

  hide(name: string) {
    if (this.isNotField(name, "hide")) super.hide(name);
  }

  show(name: string) {
    if (this.isNotField(name, "show")) super.show(name);
  }

  update(name: string, patch: Partial<FormItem>) {
    if (this.isNotField(name, "update")) super.update(name, patch);
  }

  move(name: string, position: Position) {
    if (this.isNotField(name, "move")) super.move(name, position);
  }

  private hasComponent(item: FormItem) {
    if (item.component) return true;
    warnOnce(`page.form.add("${item.name}") — a part needs a component; dropped.`);
    return false;
  }

  // One name, one owner: `fields` speaks for a field wherever the form draws it.
  private isNotField(name: string, verb: string) {
    const field = this.host.fields()?.find((one) => one.fieldname === name);
    if (!field || LAYOUT_BREAKS.has(field.fieldtype)) return true;
    warnOnce(`page.form.${verb}("${name}") — a field, not a section; ${OWNER[verb] ?? ""}.`);
    return false;
  }
}

const OWNER: Record<string, string> = {
  add: "a part needs a name of its own",
  move: "the Form Layout orders fields",
  hide: 'page.fields.hide("…") is the verb',
  show: 'page.fields.show("…") is the verb',
  update: 'page.fields.update("…") is the verb',
};

const warned = new Set<string>();

function warnOnce(message: string) {
  if (!import.meta.env.DEV || warned.has(message)) return;
  warned.add(message);
  console.warn(`[record-page] ${message}`);
}

/** Test seam: the warn-once memory is module state. */
export function resetFormWarnings(): void {
  warned.clear();
}
