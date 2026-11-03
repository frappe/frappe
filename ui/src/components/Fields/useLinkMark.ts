import { computed, inject, reactive, watch } from "vue";
import { getDocumentFields } from "../../api";
import { LinkMarksKey } from "./types";
import type { FieldMeta } from "./types";

// Marks read for values the host did not provide (picked, unsaved, or no host), keyed `Doctype::name`.
const read = reactive<Record<string, string>>({});
const asked = new Set<string>();

function readMark(target: string, name: string, field: string) {
  const key = `${target}::${name}`;
  if (asked.has(key)) return;
  asked.add(key);
  getDocumentFields<Record<string, string>>(target, name, [field])
    .then(({ data }) => data && (read[key] = data[field] ?? ""))
    .catch(() => asked.delete(key));
}

/**
 * The mark value of a Link field's current value; undefined when there is none.
 * A host that provides marks (a record) answers its saved values; any other value (picked, default, no host) is read once.
 */
export function useLinkMark(field: () => FieldMeta, value: () => unknown) {
  const provided = inject(LinkMarksKey, null);
  const keyOf = () => {
    const target = field().options;
    return value() && target ? `${target}::${value()}` : undefined;
  };
  const wanted = () => {
    const key = keyOf();
    const source = field().linkMark;
    return key && source && !provided?.value[key] ? { key, source } : undefined;
  };
  const load = () => {
    const ask = wanted();
    if (ask) readMark(field().options as string, String(value()), ask.source.field);
  };
  watch(keyOf, load, { immediate: true });
  return computed(() => {
    const key = keyOf();
    return key ? provided?.value[key] || read[key] || undefined : undefined;
  });
}
