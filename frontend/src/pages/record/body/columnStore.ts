// What the reader left behind for each body column: its width and whether it is a strip.
// The browser is the unit, keyed by user because a profile is shared and a reader's view is not.
import { ref } from "vue";
import type { Remembered } from "@/recordPage";

export const STORE_KEY = "frappe:desk:record-body-columns";

type Columns = Record<string, Remembered>;

export function useColumnStore(user: string) {
	const columns = ref<Columns>(read(user));

	function remembered(name: string): Remembered | undefined {
		return columns.value[name];
	}

	function remember(name: string, patch: Remembered) {
		columns.value = { ...columns.value, [name]: { ...columns.value[name], ...patch } };
		write(user, columns.value);
	}

	return { columns, remembered, remember };
}

function read(user: string): Columns {
	try {
		const parsed = JSON.parse(localStorage.getItem(STORE_KEY) ?? "null");
		const mine = parsed && typeof parsed === "object" ? parsed[user] : undefined;
		return mine && typeof mine === "object" ? mine : {};
	} catch {
		// Storage throws in a sandboxed frame; a value it cannot parse is no value.
		return {};
	}
}

function write(user: string, columns: Columns) {
	try {
		const parsed = JSON.parse(localStorage.getItem(STORE_KEY) ?? "null");
		const stored = parsed && typeof parsed === "object" ? parsed : {};
		localStorage.setItem(STORE_KEY, JSON.stringify({ ...stored, [user]: columns }));
	} catch {
		// Full or forbidden. The column keeps its width for this page.
	}
}
