// "Create" in a Link or Dynamic Link field's dropdown, through the host's Create. The linked
// doctype's meta and create right are read while the dropdown is open.
import { computed, inject, shallowRef, toValue } from "vue";
import type { ComputedRef, MaybeRefOrGetter, Ref } from "vue";
import { useDoctypeMeta } from "../../composables/useDoctypeMeta";
import type { DoctypeMeta } from "../../composables/useDoctypeMeta";
import { translate as __ } from "../../utils/translate";
import { typedTextField } from "../../utils/naming";
import { equalityValues } from "../../utils/equalityValues";
import type { LinkExposed } from "../Link";
import { CreateRecordKey } from "./types";

export interface UseLinkCreate {
  creatable: ComputedRef<boolean>;
  /** The Create row's label for the typed text. */
  label: (query: string) => string;
  /** Opens Create with the typed text and the field's equality filters. */
  create: (query: string) => Promise<void>;
  /** The saved record's title, for the value the field took from it. */
  title: (value: string | null) => string | undefined;
}

export function useLinkCreate(options: {
  doctype: MaybeRefOrGetter<string>;
  filters: MaybeRefOrGetter<Record<string, unknown> | undefined>;
  disabled: MaybeRefOrGetter<boolean>;
  open: Ref<boolean>;
  link: Ref<LinkExposed | null>;
  /** Takes the saved record's name, as a pick does. */
  select: (name: string) => void;
}): UseLinkCreate {
  const host = inject(CreateRecordKey, null);
  const linked = () => (host && options.open.value ? toValue(options.doctype) : "");
  const { meta } = useDoctypeMeta(linked);
  const right = host?.useRight(linked);
  const created = shallowRef<{ name: string; title?: string } | null>(null);

  const creatable = computed(() => Boolean(right?.value) && !toValue(options.disabled));

  function label(query: string): string {
    const text = query.trim();
    if (text && meta.value && typedTextField(meta.value)) return __('Create "{0}"', [text]);
    return __("Create new {0}", [__(toValue(options.doctype))]);
  }

  async function create(query: string) {
    const doctype = toValue(options.doctype);
    // Read now: the dropdown closes after this row's click, and the meta with it.
    const linkedMeta = meta.value;
    if (!host || !linkedMeta) return;
    const values = createValues(linkedMeta, toValue(options.filters) ?? {}, query.trim());
    const doc = await host.open(doctype, { values });
    options.link.value?.focus();
    if (!doc || toValue(options.doctype) !== doctype) return;
    created.value = { name: doc.name, title: titleOf(linkedMeta, doc) };
    options.select(doc.name);
    // The browser keeps the typed text's answer from before the save; this replaces it.
    options.link.value?.search(query.trim(), { fresh: true });
  }

  function title(value: string | null): string | undefined {
    return value && created.value?.name === value ? created.value.title : undefined;
  }

  return { creatable, label, create, title };
}

/** The field's equality filters on the doctype's own fields, then the typed text. */
function createValues(
  meta: DoctypeMeta,
  filters: Record<string, unknown>,
  text: string
): Record<string, unknown> {
  const values = equalityValues(wireFilters(filters), meta.fields ?? []);
  const target = typedTextField(meta);
  if (target && text) values[target] = text;
  return values;
}

/** A field's `{ fieldname: value }` or `{ fieldname: [operator, value] }` filters as wire triples. */
function wireFilters(filters: Record<string, unknown>): [string, string, unknown][] {
  return Object.entries(filters).flatMap(([fieldname, condition]): [string, string, unknown][] => {
    if (!Array.isArray(condition)) return [[fieldname, "=", condition]];
    return condition.length === 2 ? [[fieldname, String(condition[0]), condition[1]]] : [];
  });
}

function titleOf(meta: DoctypeMeta, doc: Record<string, any>): string | undefined {
  if (!meta.show_title_field_in_link || !meta.title_field) return undefined;
  return doc[meta.title_field] || undefined;
}
