// The writes the people editors make; each answer replaces one part of `docinfo` in place.
import {
	addAssignment,
	addShare,
	removeAssignment,
	removeShare,
	type Envelope,
	type Users,
} from "@framework/ui/api";
import { errorMessage, type RecordPageApi } from "@/recordPage";
import { recolourTag, seedTagColors, updateRecordTags } from "@/tagColors";
import { tagsOf } from "./people";
import { useTagSession, type TagBatch } from "./tagSession";
import type { DocInfo, PanelContext } from "./context";

type PartAnswer = Partial<DocInfo> & { users?: Users; tag_colors?: Record<string, string> };

/** What the writes read; the record menu's "Assign to…" hands it the page's own parts. */
type PeopleSource = Pick<PanelContext, "doctype" | "docname" | "docinfo" | "whileOnRecord" | "reloadDocinfo"> & {
	controller: { page: Pick<RecordPageApi, "toast"> };
};

const shared = new WeakMap<PeopleSource, ReturnType<typeof buildActions>>();

/** One set of actions per panel context, so every tag picker on the page edits the same session. */
export function peopleActions(context: PeopleSource) {
	if (!shared.has(context)) shared.set(context, buildActions(context));
	return shared.get(context)!;
}

function buildActions(context: PeopleSource) {
	const { doctype, docname, controller, docinfo, whileOnRecord } = context;
	const page = controller.page;

	async function send(write: () => Promise<Envelope<PartAnswer>>): Promise<boolean> {
		const current = whileOnRecord();
		try {
			const answer = await write();
			seedTagColors(answer.data.tag_colors);
			// An answer that outlived its record would paint the old rows onto the new one.
			if (current()) docinfo.value = mergePart(docinfo.value, answer.data);
			return true;
		} catch (caught) {
			page.toast.error(errorMessage(caught));
			return false;
		}
	}

	// One call saves the whole session; a failure toasts and shows the server's tags again.
	async function writeTags(batch: TagBatch) {
		const current = whileOnRecord();
		try {
			const answer = await updateRecordTags(doctype, docname, batch);
			if (current()) docinfo.value = mergePart(docinfo.value, answer);
		} catch (caught) {
			page.toast.error(errorMessage(caught));
			if (current()) await context.reloadDocinfo();
		}
	}

	async function recolour(tag: string, color: string) {
		try {
			await recolourTag(tag, color);
		} catch (caught) {
			page.toast.error(errorMessage(caught));
		}
	}

	return {
		tagSession: useTagSession(() => tagsOf(docinfo.value), writeTags, recolour),
		assign: (user: string) => send(() => addAssignment(doctype, docname, { user })),
		unassign: (user: string) => send(() => removeAssignment(doctype, docname, user)),
		share: (user: string) => send(() => addShare(doctype, docname, { user, read: 1, write: 1 })),
		unshare: (user: string) => send(() => removeShare(doctype, docname, user)),
	};
}

export type PeopleActions = ReturnType<typeof buildActions>;

/** The answer's part over the old one; its `users` join the map, since a removed row keeps its name. */
export function mergePart(
	docinfo: DocInfo | null,
	{ users, tag_colors: _colors, ...part }: PartAnswer
): DocInfo {
	return { ...docinfo, ...part, users: { ...docinfo?.users, ...users } };
}
