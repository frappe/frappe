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

	// Which fetch is current. Moving between modules leaves the previous one in
	// flight, and without this the slower response wins: the rail would show the
	// module the reader has left. The same guard `List.vue` and `Record.vue` already
	// carry, for the same reason.
	let generation = 0;

	watchEffect(async () => {
		const mine = ++generation;
		if (!app) {
			entries.value = [];
			return;
		}

		// `module?.value` is read HERE, synchronously, so `watchEffect` tracks it.
		// Reading it after the await would register no dependency and the rail would
		// never update again.
		const fetched = await fetchNavigation(app, module?.value);
		if (mine !== generation) return;
		entries.value = fetched;
	});

	return entries;
}
