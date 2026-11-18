// The views of one doctype from `list_views`, read again after each write to a view (`refreshSavedViews`).
import { currentSession } from "@framework/ui/useSession";
import { onScopeDispose, ref, shallowRef, watch, type ShallowRef } from "vue";
import { fetchViews, type ListedView } from "@/navigation/editor/viewPicker";
import { savedViewsRevision } from "./savedView";

/** The pointers that default to a view: the person's own and the site's. */
export type DefaultScope = "user" | "site";

export type { ListedView };

// The last answer per doctype for the session user: a second open paints at once, then reads again.
const remembered = new Map<string, ListedView[]>();
let rememberedFor: string | undefined;

function recall(doctype: string): ListedView[] | null {
	const user = currentSession()?.user.name;
	if (rememberedFor !== user) {
		rememberedFor = user;
		remembered.clear();
	}
	return remembered.get(doctype) ?? null;
}

const SHARED_READ_MS = 10_000;
type Read = { scope: string; revision: number; at: number; found: Promise<ListedView[]> };
const reads = new Map<string, Read>();
const landed = ref(0);

function shared(doctype: string, app: string, asker?: string): Promise<ListedView[]> {
	const scope = `${asker}\0${app}`;
	const last = reads.get(doctype);
	const revision = savedViewsRevision.value;
	const now = Date.now();
	if (last?.scope === scope && last.revision === revision && now - last.at < SHARED_READ_MS)
		return last.found;
	const read = { scope, revision, at: now, found: fetchViews(doctype, app) };
	reads.set(doctype, read);
	// A failed read is not shared: the next ask goes to the server.
	read.found.then(
		() => landed.value++,
		() => reads.get(doctype) === read && reads.delete(doctype),
	);
	return read.found;
}

/** Drops every remembered list. */
export function resetListedViews(): void {
	remembered.clear();
	reads.clear();
	rememberedFor = undefined;
}

export interface ListedViews {
	/** Null until the first read lands; a failed read leaves the last answer. */
	views: ShallowRef<ListedView[] | null>;
	reload: () => Promise<void>;
}

/** Reads the doctype's views now, and again after each write to a view. */
export function useListedViews(doctype: string, app: string): ListedViews {
	const views = shallowRef<ListedView[] | null>(recall(doctype));
	let asking = 0;

	async function reload() {
		const mine = ++asking;
		const asker = currentSession()?.user.name;
		try {
			const found = await shared(doctype, app, asker);
			if (mine !== asking) return;
			if (asker === rememberedFor) remembered.set(doctype, found);
			views.value = found;
		} catch {
			// With no list yet, opening the menu asks again.
		}
	}

	watch(savedViewsRevision, reload, { immediate: true });
	watch(landed, () => views.value || reload());
	onScopeDispose(() => void asking++);
	return { views, reload };
}
