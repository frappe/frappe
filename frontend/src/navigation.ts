// NAVIGATION -- what an app's chrome offers you. Deliberately a different list from
// the address table beside it.
//
// #42210 split what `boot.doctype_slugs` conflated. ADDRESSABILITY is full-bench and
// permission-independent: two colleagues must resolve a pasted URL identically, so
// the address space cannot change shape per user. NAVIGATION is per app and
// permission-filtered: a doctype you cannot read is still addressable -- you are
// refused at the record by ordinary permissions -- it is simply not offered to you.
//
// The rail derived from the address space before this, and its "permission, not
// declaration" comment was already false. It is true now.
//
// What this is NOT is the navigation MODEL. #42211 §8 retired `Navigation Section`
// without naming a replacement; a single item kind used in both rail and sidebar is
// the direction, and it is a data model rather than a decision, so it is not this
// ticket's. This is the smallest honest thing that keeps the chrome rendering now
// that the table it read has moved: the owning app's doctypes, filtered.

import { ref, watchEffect, type Ref } from "vue";

export type NavigationEntry = { doctype: string; slug: string; module: string };

export function fetchNavigation(
  app: string,
  module?: string
): Promise<NavigationEntry[]> {
  const params = new URLSearchParams({ app });
  if (module) params.set("module", module);
  return fetch(`/api/method/frappe.shell.doctypes.get_navigation?${params}`)
    .then((res) => (res.ok ? res.json() : null))
    .then((body) => body?.message ?? [])
    .catch(() => []);
}

/** Reactive navigation for a prefix, optionally narrowed to one module. */
export function useNavigation(
  app: string | null,
  module?: Ref<string | undefined>
) {
  const entries = ref<NavigationEntry[]>([]);

  watchEffect(async () => {
    if (!app) {
      entries.value = [];
      return;
    }
    entries.value = await fetchNavigation(app, module?.value);
  });

  return entries;
}
