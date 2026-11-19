// How a doctype names a new record, for the text a person types as its name.

/** The insert body's key for a typed name; a `name` key would skip the naming rule. */
export const NEW_NAME = "__newname";

interface Naming {
  autoname?: string;
  title_field?: string;
}

export function isNamedByPrompt<T extends Naming>(meta: T | null | undefined): meta is T & { autoname: string } {
  return meta?.autoname?.toLowerCase() === "prompt";
}

/** Where typed text goes in a new record: a `field:` rule's field, the prompt name, or the title field. */
export function typedTextField(meta: Naming): string | null {
  const autoname = meta.autoname ?? "";
  if (autoname.toLowerCase().startsWith("field:")) return autoname.slice("field:".length) || null;
  if (isNamedByPrompt(meta)) return NEW_NAME;
  return meta.title_field || null;
}
