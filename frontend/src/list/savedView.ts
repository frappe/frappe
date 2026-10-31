// The saved view a list address names, looked up by its doctype and key as the person sees it.
import { isApiError, runMethod } from "@framework/ui/api";
import { onScopeDispose, shallowRef, watch, type ShallowRef } from "vue";

const FIND = "frappe.desk.doctype.doctype_view.api.find";

export interface SavedView {
	key: string;
	label: string;
	type: string;
}

export interface SavedViewHandle {
	/** Null while the lookup runs, after a refusal, and on an address that names no view. */
	view: ShallowRef<SavedView | null>;
	/** The server's refusal; `isMissing` tells a view the person cannot open from a failed read. */
	failure: ShallowRef<unknown>;
	retry: () => Promise<void>;
}

/** Looks the view up again whenever the address names another one; an older answer is dropped. */
export function useSavedView(doctype: () => string | null, key: () => string | null): SavedViewHandle {
	const view = shallowRef<SavedView | null>(null);
	const failure = shallowRef<unknown>(null);
	let asking: AbortController | undefined;

	async function load() {
		asking?.abort();
		view.value = null;
		failure.value = null;
		const [doctypeName, viewKey] = [doctype(), key()];
		if (!doctypeName || !viewKey) return;

		const current = (asking = new AbortController());
		try {
			const { data } = await runMethod<SavedView>(
				FIND,
				{ doctype: doctypeName, key: viewKey },
				{ http: "GET", signal: current.signal }
			);
			if (!current.signal.aborted) view.value = data;
		} catch (error) {
			if (!current.signal.aborted) failure.value = error;
		}
	}

	watch(() => [doctype(), key()], load, { immediate: true });
	onScopeDispose(() => asking?.abort());

	return { view, failure, retry: load };
}

/** The view does not exist, or the person cannot see it: both read as one not-found page. */
export function isMissing(failure: unknown): boolean {
	return isApiError(failure) && failure.status === 404;
}
