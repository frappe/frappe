// The one way to open Create for a doctype. The page layer registers the dialog, which picks
// itself or the full-page new record; the shell keeps the open requests above any page.
import { markRaw, readonly, shallowRef, type Component } from "vue";

export type CreatedDoc = Record<string, any>;

export interface CreateOptions {
	/** The values the new record starts with, over the server defaults. */
	values?: Record<string, any>;
}

/** One open Create, as the registered dialog receives it. */
export interface CreateRequest {
	id: number;
	doctype: string;
	values: Record<string, any>;
	/** Resolves the caller with the saved record or `null`; only the first call counts. */
	settle: (doc: CreatedDoc | null) => void;
	/** Takes the request off the stack, after the dialog's leave transition. */
	dismiss: () => void;
}

const requests = shallowRef<CreateRequest[]>([]);
let dialog: Component | null = null;
let nextId = 0;

/** The open requests, oldest first. */
export const createRequests = readonly(requests);

/** `main.ts` registers the dialog before anything can open Create. */
export function registerCreateDialog(component: Component) {
	dialog = markRaw(component);
}

export function createDialog(): Component | null {
	return dialog;
}

/** Resolves with the saved record, or `null` when the person dismisses or goes to the full page. */
export function openCreate(
	doctype: string,
	options: CreateOptions = {}
): Promise<CreatedDoc | null> {
	if (!dialog) throw new Error("openCreate was called before the Create dialog was registered");
	return new Promise((resolve) => {
		const id = nextId++;
		let settled = false;
		const request: CreateRequest = {
			id,
			doctype,
			values: { ...options.values },
			settle: (doc) => {
				if (settled) return;
				settled = true;
				resolve(doc);
			},
			dismiss: () => (requests.value = requests.value.filter((one) => one.id !== id)),
		};
		requests.value = [...requests.value, request];
	});
}

/** Every open request resolves `null` and leaves at once, as on a route change. */
export function closeCreates() {
	for (const request of requests.value) request.settle(null);
	requests.value = [];
}
