// What an app contains: per app and permission-filtered, unlike the address table beside
// it. Fetched by the pages that show it, never by the rail, which arrives in boot.

import { ref, watchEffect, type Ref } from "vue";
import { runMethod } from "@framework/ui/api";

export type ContentEntry = { doctype: string; slug: string; module: string };

/**
 * Throws on failure: an empty list is a real answer here and must not be forged.
 */
export async function fetchContents(
	app: string,
	module?: string
): Promise<ContentEntry[]> {
	const args: { app: string; module?: string } = { app };
	if (module) args.module = module;

	const response = await runMethod<ContentEntry[]>(
		"frappe.shell.doctypes.get_contents",
		args,
		{ http: "GET" }
	);
	return response.data;
}

/**
 * Reactive contents for a prefix, optionally narrowed to one module. `loading` and `error`
 * let a caller tell "none" from "not yet" and "failed"; `reload` reads them again.
 */
export function useContents(
	app: string | null,
	module?: Ref<string | undefined>
) {
	const entries = ref<ContentEntry[]>([]);
	const loading = ref(false);
	const error = ref<unknown>(null);

	// The slower of two in-flight fetches must not win after the reader has moved on.
	let generation = 0;

	async function read(moduleSlug: string | undefined) {
		const mine = ++generation;

		// Cleared before the await: the old links under the new heading are clickable.
		entries.value = [];
		error.value = null;

		if (!app) {
			loading.value = false;
			return;
		}

		loading.value = true;
		try {
			const fetched = await fetchContents(app, moduleSlug);
			if (mine !== generation) return;
			entries.value = fetched;
		} catch (caught) {
			if (mine !== generation) return;
			error.value = caught;
		}

		loading.value = false;
	}

	// `module?.value` is read here, synchronously, so `watchEffect` tracks it.
	watchEffect(() => read(module?.value));

	return { entries, loading, error, reload: () => read(module?.value) };
}
