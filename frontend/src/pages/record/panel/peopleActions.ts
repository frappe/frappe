// The writes the people editors make; each answer replaces one part of `docinfo` in place.
import {
	addAssignment,
	addShare,
	addTag,
	removeAssignment,
	removeShare,
	removeTag,
	type Envelope,
	type Users,
} from "@framework/ui/api";
import { errorMessage, type RecordPageApi } from "@/recordPage";
import type { DocInfo, PanelContext } from "./context";

type PartAnswer = Partial<DocInfo> & { users?: Users };

/** What the writes read; the record menu's "Assign to…" hands it the page's own parts. */
type PeopleSource = Pick<PanelContext, "doctype" | "docname" | "docinfo" | "whileOnRecord"> & {
	controller: { page: Pick<RecordPageApi, "toast"> };
};

export function peopleActions(context: PeopleSource) {
	const { doctype, docname, controller, docinfo, whileOnRecord } = context;
	const page = controller.page;

	async function send(write: () => Promise<Envelope<PartAnswer>>) {
		const current = whileOnRecord();
		try {
			const answer = await write();
			// An answer that outlived its record would paint the old rows onto the new one.
			if (current()) docinfo.value = mergePart(docinfo.value, answer.data);
		} catch (caught) {
			page.toast.error(errorMessage(caught));
		}
	}

	return {
		assign: (user: string) => send(() => addAssignment(doctype, docname, { user })),
		unassign: (user: string) => send(() => removeAssignment(doctype, docname, user)),
		share: (user: string) => send(() => addShare(doctype, docname, { user, read: 1, write: 1 })),
		unshare: (user: string) => send(() => removeShare(doctype, docname, user)),
		addTag: (tag: string) => send(() => addTag(doctype, docname, tag)),
		removeTag: (tag: string) => send(() => removeTag(doctype, docname, tag)),
	};
}

export type PeopleActions = ReturnType<typeof peopleActions>;

/** The answer's part over the old one; its `users` join the map, since a removed row keeps its name. */
export function mergePart(docinfo: DocInfo | null, { users, ...part }: PartAnswer): DocInfo {
	return { ...docinfo, ...part, users: { ...docinfo?.users, ...users } };
}
