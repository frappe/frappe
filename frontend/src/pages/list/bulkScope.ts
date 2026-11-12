// The selection's scope as the bulk acts read it: the words their palette labels carry and the value they run on.
import type { Ref } from "vue";
import { __ } from "@/i18n";

export interface BulkScopeView {
	/** An act's label with the scope, such as "Delete 3 selected". */
	label: (label: string) => string;
	/** What an action runs on; a copy, so a later selection change does not reach a run in flight. */
	selected: () => string[];
}

export function bulkScopeOf(selection: Ref<string[]>): BulkScopeView {
	return {
		label: (label) => __("{0} {1} selected", [label, selection.value.length]),
		selected: () => [...selection.value],
	};
}
