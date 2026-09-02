// CONTENTS -- what an app CONTAINS. Deliberately a different list from the address
// table beside it, and a different list from the rail.
//
// #42210 split what `boot.doctype_slugs` conflated. ADDRESSABILITY is full-bench and
// permission-independent: two colleagues must resolve a pasted URL identically, so
// the address space cannot change shape per user. CONTENTS are per app and
// permission-filtered: a doctype you cannot read is still addressable -- you are
// refused at the record by ordinary permissions -- it is simply not offered to you.
//
// The rail read this until #42357, and no longer does. The rail is AUTHORED
// navigation, resolved server-side and delivered in boot, because a rail click must
// not cost a request. This list is DERIVED, and it is fetched by the two pages that
// show it -- the app home and a module page -- because arriving somewhere and paying
// one request for what is there is ordinary. The two lists disagree on purpose:
// measured across ERPNext, 107 doctypes sit on a module page and not in that module's
// sidebar, while 101 sidebar links point outside their module. The page answers what
// does this contain; the rail answers what do you do here.

import { ref, watchEffect, type Ref } from "vue";

export type ContentEntry = { doctype: string; slug: string; module: string };

/**
 * THROWS rather than answering empty. A swallowed failure is indistinguishable from
 * "you can read nothing here", which is a real answer — so the caller would render a
 * confident, false "0 doctypes you can read" over a request that never landed, and an
 * empty rail that looks like an empty app.
 */
export async function fetchContents(
	app: string,
	module?: string
): Promise<ContentEntry[]> {
	const params = new URLSearchParams({ app });
	if (module) params.set("module", module);

	const res = await fetch(
		`/api/method/frappe.shell.doctypes.get_contents?${params}`
	);
	if (!res.ok) throw new Error(`Contents failed with ${res.status}`);
	return (await res.json()).message ?? [];
}

/**
 * Reactive contents for a prefix, optionally narrowed to one module.
 *
 * `loading` and `failed` are not decoration. An empty list is a REAL answer here — a
 * module you can read nothing in — so a caller that cannot tell "none" from "not yet"
 * or from "the request failed" has to assert one of them, and "0 doctypes you can
 * read" is a false statement to put under either.
 */
export function useContents(
	app: string | null,
	module?: Ref<string | undefined>
) {
	const entries = ref<ContentEntry[]>([]);
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
			const fetched = await fetchContents(app, module?.value);
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
