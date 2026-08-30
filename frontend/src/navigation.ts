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

/**
 * THROWS rather than answering empty. A swallowed failure is indistinguishable from
 * "you can read nothing here", which is a real answer — so the caller would render a
 * confident, false "0 doctypes you can read" over a request that never landed, and an
 * empty rail that looks like an empty app.
 */
export async function fetchNavigation(
	app: string,
	module?: string
): Promise<NavigationEntry[]> {
	const params = new URLSearchParams({ app });
	if (module) params.set("module", module);

	const res = await fetch(
		`/api/method/frappe.shell.doctypes.get_navigation?${params}`
	);
	if (!res.ok) throw new Error(`Navigation failed with ${res.status}`);
	return (await res.json()).message ?? [];
}

/**
 * Reactive navigation for a prefix, optionally narrowed to one module.
 *
 * `loading` and `failed` are not decoration. An empty list is a REAL answer here — a
 * module you can read nothing in — so a caller that cannot tell "none" from "not yet"
 * or from "the request failed" has to assert one of them, and "0 doctypes you can
 * read" is a false statement to put under either.
 */
export function useNavigation(
	app: string | null,
	module?: Ref<string | undefined>
) {
	const entries = ref<NavigationEntry[]>([]);
	const loading = ref(false);
	const failed = ref(false);

	// Which fetch is current. Moving between modules leaves the previous one in
	// flight, and without this the slower response wins: the page would settle on the
	// module the reader has left. The same guard `List.vue` and `Record.vue` already
	// carry, for the same reason.
	let generation = 0;

	watchEffect(async () => {
		const mine = ++generation;

		// Cleared BEFORE the await, not after it. Keeping the old entries on screen
		// while the new ones load puts the new module's heading above the previous
		// module's links -- briefly, and clickably, which is worse than empty.
		entries.value = [];
		failed.value = false;

		if (!app) {
			loading.value = false;
			return;
		}

		loading.value = true;

		// `module?.value` is read HERE, synchronously, so `watchEffect` tracks it.
		// Reading it after the await would register no dependency and the list would
		// never update again.
		try {
			const fetched = await fetchNavigation(app, module?.value);
			if (mine !== generation) return;
			entries.value = fetched;
		} catch {
			if (mine !== generation) return;
			// Reported, not swallowed. The list stays empty either way; what changes is
			// that the caller can say "could not load" instead of "there is nothing".
			failed.value = true;
		}

		loading.value = false;
	});

	return { entries, loading, failed };
}
