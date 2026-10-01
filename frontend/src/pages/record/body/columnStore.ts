// What the reader left behind for each body column: its width and whether it is a strip.
// Kept in the browser per user, keyed by column name.
import { ref } from "vue";
import { browserMemory } from "@/browserMemory";
import type { Remembered } from "@/recordPage";

type Columns = Record<string, Remembered>;

export function useColumnStore(user: string) {
	const memory = browserMemory("record-body-columns", user, isColumns);
	const columns = ref<Columns>(memory.recall() ?? {});

	function remembered(name: string): Remembered | undefined {
		return columns.value[name];
	}

	function remember(name: string, patch: Remembered) {
		columns.value = { ...columns.value, [name]: { ...columns.value[name], ...patch } };
		memory.remember(columns.value);
	}

	return { columns, remembered, remember };
}

function isColumns(value: unknown): value is Columns {
	return !!value && typeof value === "object" && !Array.isArray(value);
}
