// The writes the people editors make; each answer replaces one part of `docinfo` in place.
import {
	addAssignment,
	addFollow,
	addShare,
	addTag,
	removeAssignment,
	removeFollow,
	removeShare,
	removeTag,
	type Envelope,
	type Users,
} from "@framework/ui/api";
import { errorMessage } from "@/recordPage";
import type { DocInfo, PanelContext } from "./context";

type PartAnswer = Partial<DocInfo> & { users?: Users };

export function peopleActions(context: PanelContext) {
	const { doctype, docname, controller, docinfo, whileOnRecord } = context;
	const page = controller.page;

	async function send(write: () => Promise<Envelope<PartAnswer>>) {
		const current = whileOnRecord();
		try {
			const answer = await write();
			// An answer that outlived its record would paint the old rows onto the new one.
			if (current()) docinfo.value = mergePart(docinfo.value, answer.data);
			return answer;
		} catch (caught) {
			page.toast.error(errorMessage(caught));
		}
	}

	// The server declines a follow without failing, and says why beside the data.
	async function follow() {
		const answer = await send(() => addFollow(doctype, docname));
		if (!answer || answer.data.follows) return;
		const message = messageOf(answer);
		if (message) page.toast.error(message);
	}

	return {
		assign: (user: string) => send(() => addAssignment(doctype, docname, { user })),
		unassign: (user: string) => send(() => removeAssignment(doctype, docname, user)),
		share: (user: string) => send(() => addShare(doctype, docname, { user, read: 1, write: 1 })),
		unshare: (user: string) => send(() => removeShare(doctype, docname, user)),
		addTag: (tag: string) => send(() => addTag(doctype, docname, tag)),
		removeTag: (tag: string) => send(() => removeTag(doctype, docname, tag)),
		follow,
		unfollow: () => send(() => removeFollow(doctype, docname)),
	};
}

/** The first message a v2 answer carries beside its data. */
function messageOf(answer: Envelope<unknown>): string | undefined {
	const [first] = (answer.messages as { message?: string }[] | undefined) ?? [];
	return first?.message;
}

export type PeopleActions = ReturnType<typeof peopleActions>;

/** The answer's part over the old one; its `users` join the map, since a removed row keeps its name. */
export function mergePart(docinfo: DocInfo | null, { users, ...part }: PartAnswer): DocInfo {
	return { ...docinfo, ...part, users: { ...docinfo?.users, ...users } };
}
