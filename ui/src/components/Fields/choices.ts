import type { FieldMeta, OptionChoice } from "./types";

/** The choices of a `Select` or `Autocomplete`: a script's labelled pairs, else the newline-joined `options`. */
export function fieldChoices(field: FieldMeta, tidy = false): OptionChoice[] {
  if (field.choices) return tidy ? field.choices.filter((one) => one.value.trim()) : field.choices;
  const lines = (field.options ?? "").split("\n");
  return (tidy ? lines.map((line) => line.trim()).filter(Boolean) : lines).map((value) => ({
    label: value,
    value,
  }));
}
