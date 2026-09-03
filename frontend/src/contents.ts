// What an app contains: per app and permission-filtered, unlike the address table beside
// it. Fetched by the pages that show it, never by the rail, which arrives in boot.

import { ref, watchEffect, type Ref } from "vue";

export type ContentEntry = { doctype: string; slug: string; module: string };

/**
  * Throws on failure: an empty list is a real answer here and must not be forged.
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
  * Reactive contents for a prefix, optionally narrowed to one module. `loading` and `failed`
  * let a caller tell "none" from "not yet" and "failed".
 */
export function useContents(
	app: string | null,
	module?: Ref<string | undefined>
) {
	const entries = ref<ContentEntry[]>([]);
	const loading = ref(false);
	const failed = ref(false);

	// The slower of two in-flight fetches must not win after the reader has moved on.
	let generation = 0;

	watchEffect(async () => {
		const mine = ++generation;

		// Cleared before the await: the old links under the new heading are clickable.
		entries.value = [];
		failed.value = false;

		if (!app) {
			loading.value = false;
			return;
		}

		loading.value = true;

		// `module?.value` is read synchronously so `watchEffect` tracks it; a read after the
		// await registers no dependency.
		try {
			const fetched = await fetchContents(app, module?.value);
			if (mine !== generation) return;
			entries.value = fetched;
		} catch {
			if (mine !== generation) return;
			failed.value = true;
		}

		loading.value = false;
	});

	return { entries, loading, failed };
}
