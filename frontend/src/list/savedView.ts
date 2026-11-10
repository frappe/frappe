// The view a list address names, looked up by its doctype and key as the person sees it: a saved
// view, or a view type's plain view at its type's name.
import { isApiError, runMethod } from "@framework/ui/api";
import { currentSession } from "@framework/ui/useSession";
import { onScopeDispose, shallowRef, watch, type ShallowRef } from "vue";

const FIND = "frappe.desk.doctype.doctype_view.api.find";

export type ViewLayer = "own" | "site" | "app";

export interface SavedView {
	key: string;
	label: string;
	type: string;
	/** Null for a view type's plain view. */
	layer: ViewLayer | null;
	/** False when the view's type does not fit the doctype. */
	applies: boolean;
}

export interface SavedViewHandle {
	/** Null while the lookup runs, after a refusal, and on an address that names no view. */
	view: ShallowRef<SavedView | null>;
	/** The server's refusal; `isMissing` tells a view the person cannot open from a failed read. */
	failure: ShallowRef<unknown>;
	retry: () => Promise<void>;
}

// The last answer per doctype and key, so a return visit paints at once and looks up again behind it.
// What one user may open is not what the next may, so another session user starts it empty.
const found = new Map<string, SavedView>();
let foundFor: string | undefined;

function remembered(doctype: string, key: string): SavedView | null {
	const user = currentSession()?.user.name;
	if (foundFor !== user) {
		foundFor = user;
		found.clear();
	}
	return found.get(`${doctype}\0${key}`) ?? null;
}

/** Drops every remembered answer, so one test's views cannot reach the next. */
export function resetSavedViews(): void {
	found.clear();
	foundFor = undefined;
}

/** Looks the view up again whenever the address names another one; an older answer is dropped. */
export function useSavedView(doctype: () => string | null, key: () => string | null): SavedViewHandle {
	const view = shallowRef<SavedView | null>(null);
	const failure = shallowRef<unknown>(null);
	let asking: AbortController | undefined;

	async function load() {
		asking?.abort();
		failure.value = null;
		const [doctypeName, viewKey] = [doctype(), key()];
		view.value = doctypeName && viewKey ? remembered(doctypeName, viewKey) : null;
		if (!doctypeName || !viewKey) return;

		const current = (asking = new AbortController());
		const asker = currentSession()?.user.name;
		try {
			const { data } = await runMethod<SavedView>(
				FIND,
				{ doctype: doctypeName, key: viewKey },
				{ http: "GET", signal: current.signal }
			);
			if (current.signal.aborted) return;
			if (asker === foundFor) found.set(`${doctypeName}\0${viewKey}`, data);
			view.value = data;
		} catch (error) {
			if (current.signal.aborted) return;
			found.delete(`${doctypeName}\0${viewKey}`);
			view.value = null;
			failure.value = error;
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
