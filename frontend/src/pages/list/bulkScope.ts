// The selection's scope as the bulk acts read it: the words their palette labels carry and the value they run on.
import type { Ref } from "vue";
import { __ } from "@/i18n";

export interface BulkScopeView {
	/** The scope in words, such as "3 selected". */
	text: () => string;
	/** What an action runs on; a copy, so a later selection change does not reach a run in flight. */
	selected: () => string[];
}

export function bulkScopeOf(selection: Ref<string[]>): BulkScopeView {
	return {
		text: () => __("{0} selected", [selection.value.length]),
		selected: () => [...selection.value],
	};
}

/** An act's label with the scope, such as "Delete 3 selected". */
export function scopedLabel(label: string, scope: BulkScopeView) {
	return __("{0} {1}", [label, scope.text()], "A bulk action's label with its scope");
}
