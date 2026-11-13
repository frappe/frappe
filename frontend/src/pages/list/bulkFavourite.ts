// The bar's Favourite: one `bulk_favourites` call, reported by the shell like the other bulk acts.
import { bulkCollaborate, type BulkSelection } from "@framework/ui/api";
import { computed, type Ref } from "vue";
import { __ } from "@/i18n";
import { isStarred } from "@/list/favouriteStars";
import type { BulkScope } from "@/list/useBulkScope";
import type { ListPageAction } from "@/listPage/types";
import { runBulk } from "@/shell/bulkOutcome";

export interface BulkFavourite {
	/** Favourite and Unfavourite as bar buttons, and Unfavourite in More under "Select all". */
	items: () => ListPageAction[];
	/** Whether `run` is one of these items': they send the bar's whole scope. */
	takesScope: (run: unknown) => boolean;
}

interface Options {
	doctype: string;
	scope: BulkScope;
	selection: Ref<string[]>;
	user: string;
	reload: () => void;
}

export function useBulkFavourite({ doctype, scope, selection, user, reload }: Options): BulkFavourite {
	// "Select all" holds no row names, so it never reads as starred: its button adds.
	const allStarred = computed(() => {
		const { names } = scope.selected() as { names?: string[] };
		return Boolean(names?.length) && names!.every((name) => isStarred(doctype, name, user));
	});

	const run = (add: boolean) => () => send(add, scope.selected());
	const runs = [run(true), run(false), run(false)];

	function send(add: boolean, target: BulkSelection) {
		return runBulk({
			label: add ? __("Favourite") : __("Unfavourite"),
			doctype,
			send: (names) => bulkCollaborate(doctype, "favourites", add ? "POST" : "DELETE", names ? { names } : target),
			select: (names) => (selection.value = names),
			finished: reload,
		});
	}

	const items = (): ListPageAction[] => [
		{
			name: "favourite_records",
			label: __("Favourite"),
			icon: "lucide-star",
			group: "collaborate",
			right: "read",
			button: true,
			when: () => !allStarred.value,
			run: runs[0],
		},
		{
			name: "unfavourite_records",
			label: __("Unfavourite"),
			icon: "lucide-star-off",
			group: "collaborate",
			right: "read",
			button: true,
			when: () => allStarred.value,
			run: runs[1],
		},
		{
			name: "unfavourite_matching",
			label: __("Unfavourite"),
			icon: "lucide-star-off",
			group: "collaborate",
			right: "read",
			when: () => scope.all.value,
			run: runs[2],
		},
	];

	return { items, takesScope: (candidate) => runs.includes(candidate as never) };
}
