// The last number each series key counted to, read from the site for the next-name previews. A
// DocType not yet saved has none, so its previews start at 1.
import { ref, watch, type Ref } from "vue";
import { runMethod } from "@framework/ui/api";
import { seriesPrefixes } from "./namingPattern";
import type { SettingsView } from "./settingsView";

const COUNTERS = "frappe.desk.doctype_editor.naming.get_series_counters";

export function useSeriesCounters(view: SettingsView, patterns: () => string[]): Ref<Record<string, number>> {
	const counters = ref<Record<string, number>>({});
	watch(
		// JSON, not a joined string: a `format:` counter's key is "", which a join would drop. A first
		// save ends `pending` with the same keys, so it is part of the source too.
		() => JSON.stringify({
			pending: view.settings.pending,
			prefixes: [...new Set(patterns().flatMap((pattern) => seriesPrefixes(pattern, new Date())))].sort(),
		}),
		(watched, _old, onCleanup) => {
			const { pending, prefixes }: { pending: boolean; prefixes: string[] } = JSON.parse(watched);
			if (pending || !prefixes.length || prefixes.every((prefix) => prefix in counters.value)) return;
			const timer = setTimeout(() => void read(prefixes), 300);
			onCleanup(() => clearTimeout(timer));
		},
		{ immediate: true },
	);

	async function read(prefixes: string[]) {
		const args = { doctype: view.doctype, mode: view.mode, prefixes: JSON.stringify(prefixes) };
		// A failed read leaves the previews counting from 1; they are a hint, not the name.
		const counted = await runMethod<Record<string, number>>(COUNTERS, args, { http: "GET" }).catch(() => null);
		if (counted) counters.value = { ...counters.value, ...counted.data };
	}

	return counters;
}
