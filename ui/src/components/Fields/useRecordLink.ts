// The record a Link or Dynamic Link value names, through the host's `RecordLinkKey`.
import { computed, inject, toValue } from "vue";
import type { ComputedRef, MaybeRefOrGetter } from "vue";
import { RecordLinkKey } from "./types";

export interface UseRecordLink {
  /** The record's address; `null` with no value, no doctype, no host or no route. */
  href: ComputedRef<string | null>;
  open: () => void;
}

export function useRecordLink(
  doctype: MaybeRefOrGetter<string>,
  name: MaybeRefOrGetter<string | null>
): UseRecordLink {
  const host = inject(RecordLinkKey, null);

  const href = computed(() => {
    const target = toValue(doctype);
    const value = toValue(name);
    return host && target && value ? host.href(target, value) : null;
  });

  function open() {
    const value = toValue(name);
    if (host && value) host.open(toValue(doctype), value);
  }

  return { href, open };
}
