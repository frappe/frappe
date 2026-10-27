// The star on a list page: whether the person starred the list, or the saved view on show, and the toggle.
import { runMethod } from "@framework/ui/api";
import { computed, type ComputedRef } from "vue";
import { useListSettings } from "./useListSettings";

const TOGGLE = "frappe.desk.doctype.favourite.favourite.toggle_favourite";

export interface ListFavourite {
	favourited: ComputedRef<boolean>;
	/** Clicks queue, so each reads the state the one before it left. */
	toggle: () => Promise<void>;
}

/** `view` is the saved view on show, or null on the plain list. */
export function useListFavourite(doctype: string, view: () => string | null): ListFavourite {
	const settings = useListSettings(doctype);
	const favourited = computed(() => {
		const name = view();
		const { list, views } = settings.favourites.value;
		return name === null ? list : views.includes(name);
	});

	let queue = Promise.resolve();

	function toggle() {
		const turn = queue.then(async () => {
			const name = view();
			const adding = !favourited.value;
			await runMethod(TOGGLE, targetOf(doctype, name, adding), { nullable: true });
			settings.markFavourite(name, adding);
		});
		queue = turn.catch(() => undefined);
		return turn;
	}

	return { favourited, toggle };
}

function targetOf(doctype: string, view: string | null, add: boolean) {
	return view === null
		? { doctype: "DocType", name: doctype, add }
		: { doctype: "Doctype View", name: view, add };
}
