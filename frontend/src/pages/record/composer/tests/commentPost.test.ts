// The comment send: a pending row at once, the server's key and time on it, and the draft back on a failure.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { addComment, pending, addPendingActivity } = vi.hoisted(() => {
	const pending = { resolve: vi.fn(), drop: vi.fn() };
	return {
		addComment: vi.fn(),
		pending,
		addPendingActivity: vi.fn((..._args: unknown[]) => pending),
	};
});
vi.mock("@framework/ui/api", () => ({ addComment }));
vi.mock("@framework/ui/ActivityTimeline", () => ({ addPendingActivity }));

import {
	activeWriter,
	closeComposer,
	composerDraft,
	composerState,
	draftRevision,
	openComposer,
	preferredWindow,
	registerComposerRecord,
	saveComposerDraft,
} from "@/shell/composer";
import { postComment } from "../commentPost";

const AUTHOR = {
	name: "ann@example.com",
	email: "ann@example.com",
	fullname: "Ann",
};
const FILE = {
	name: "F-9",
	file_name: "brief.pdf",
	file_url: "/private/files/brief.pdf",
	file_type: "application/pdf",
};
const DRAFT = { content: "<p>Looks good</p>", attachments: [FILE] };

let record = 0;
const pages: (() => void)[] = [];

// A context the record's page registers, as it does while it is mounted.
function fakeContext(docname = `NOTE-${++record}`) {
	const context = {
		doctype: "Note",
		docname,
		title: docname,
		perms: {},
		toast: { error: vi.fn(), success: vi.fn() },
		firePost: vi.fn(async () => {}),
	};
	pages.push(registerComposerRecord("Note", docname, context));
	return context;
}

function opened(context: ReturnType<typeof fakeContext>) {
	openComposer("Note", context.docname, "comment");
	saveComposerDraft("Note", context.docname, "comment", DRAFT);
}

beforeEach(() => {
	vi.clearAllMocks();
	closeComposer();
});
afterEach(() => {
	for (const unregister of pages.splice(0)) unregister();
});

describe("postComment", () => {
	it("collapses, clears the draft and adds a pending row in the reader's name before the answer", async () => {
		const context = fakeContext();
		opened(context);
		addComment.mockReturnValue(new Promise(() => {}));
		void postComment(context, AUTHOR, DRAFT);
		expect(activeWriter("Note", context.docname)).toBe("");
		expect(composerDraft("Note", context.docname, "comment")).toBeUndefined();
		expect(addPendingActivity).toHaveBeenCalledWith("Note", context.docname, {
			type: "comment",
			author: AUTHOR,
			data: {
				name: "",
				content: DRAFT.content,
				attachments: [
					{
						file_url: FILE.file_url,
						file_name: FILE.file_name,
						is_private: 1,
					},
				],
			},
		});
		expect(addPendingActivity.mock.calls[0][2]).not.toHaveProperty("timestamp");
		expect(addComment).toHaveBeenCalledWith("Note", context.docname, DRAFT.content, {
			attachments: ["F-9"],
		});
	});

	it("gives the row its server key and time, then fires onPost with the key", async () => {
		const context = fakeContext();
		addComment.mockResolvedValue({
			data: {
				comments: [
					{ name: "C-1", creation: "2026-09-01 10:00:00" },
					{ name: "C-2", creation: "2026-09-23 12:00:00" },
				],
				added: "C-2",
			},
		});
		await postComment(context, AUTHOR, DRAFT);
		expect(pending.resolve).toHaveBeenCalledWith("comment:C-2", "2026-09-23 12:00:00");
		expect(context.firePost).toHaveBeenCalledWith("comment:C-2");
		expect(pending.drop).not.toHaveBeenCalled();
	});

	it("resolves the row for a writer away from its record, which has no onPost", async () => {
		const { firePost: _none, ...away } = fakeContext();
		pages.pop()?.();
		addComment.mockResolvedValue({ data: { comments: [], added: "C-3" } });
		await postComment(away, AUTHOR, DRAFT);
		expect(pending.resolve).toHaveBeenCalledWith("comment:C-3", undefined);
	});

	it("fires no onPost when the record's page goes before the answer", async () => {
		const context = fakeContext();
		let answer: (value: unknown) => void = () => {};
		addComment.mockReturnValue(new Promise((resolve) => (answer = resolve)));
		const sent = postComment(context, AUTHOR, DRAFT);
		pages.pop()?.();
		answer({ data: { comments: [], added: "C-4" } });
		await sent;
		expect(pending.resolve).toHaveBeenCalledWith("comment:C-4", undefined);
		expect(context.firePost).not.toHaveBeenCalled();
	});

	it("fires the page's onPost when the page is back before the answer", async () => {
		const { firePost: _none, ...away } = fakeContext();
		pages.pop()?.();
		let answer: (value: unknown) => void = () => {};
		addComment.mockReturnValue(new Promise((resolve) => (answer = resolve)));
		const sent = postComment(away, AUTHOR, DRAFT);
		const back = fakeContext(away.docname);
		answer({ data: { comments: [], added: "C-5" } });
		await sent;
		expect(back.firePost).toHaveBeenCalledWith("comment:C-5");
	});

	it("leaves the row for the feed to retire when the answer names no comment", async () => {
		const context = fakeContext();
		addComment.mockResolvedValue({ data: { comments: [] } });
		await postComment(context, AUTHOR, DRAFT);
		expect(pending.drop).not.toHaveBeenCalled();
		expect(pending.resolve).not.toHaveBeenCalled();
		expect(context.firePost).not.toHaveBeenCalled();
	});

	it("takes the row back, restores the draft, reopens and says why on a failure", async () => {
		const context = fakeContext();
		opened(context);
		addComment.mockRejectedValue(new Error("Not permitted"));
		await postComment(context, AUTHOR, DRAFT);
		expect(pending.drop).toHaveBeenCalled();
		expect(pending.resolve).not.toHaveBeenCalled();
		expect(context.firePost).not.toHaveBeenCalled();
		expect(composerDraft("Note", context.docname, "comment")).toEqual(DRAFT);
		expect(activeWriter("Note", context.docname)).toBe("comment");
		expect(context.toast.error).toHaveBeenCalledWith("Not permitted");
	});

	it("reopens a floating writer floating, the reader's own choice untouched", async () => {
		const context = fakeContext();
		openComposer("Note", context.docname, "comment", undefined, "floating");
		addComment.mockRejectedValue(new Error("Offline"));
		await postComment(context, AUTHOR, DRAFT);
		expect(activeWriter("Note", context.docname)).toBe("comment");
		expect(composerState.window).toBe("floating");
		expect(preferredWindow()).toBe("docked");
	});

	it("puts the failed draft before a newer one in the open writer, and redraws it", async () => {
		const context = fakeContext();
		const { docname } = context;
		const other = { ...FILE, name: "F-10", file_url: "/private/files/other.pdf" };
		let fail: (error: Error) => void = () => {};
		addComment.mockReturnValue(new Promise((_, reject) => (fail = reject)));
		const sent = postComment(context, AUTHOR, DRAFT);
		opened(context);
		saveComposerDraft("Note", docname, "comment", {
			content: "<p>Also this</p>",
			attachments: [other, FILE],
		});
		const revision = draftRevision("Note", docname, "comment");
		fail(new Error("Offline"));
		await sent;
		expect(composerDraft("Note", docname, "comment")).toEqual({
			content: "<p>Looks good</p><p>Also this</p>",
			attachments: [FILE, other],
		});
		expect(draftRevision("Note", docname, "comment")).toBe(revision + 1);
		expect(activeWriter("Note", docname)).toBe("comment");
	});

	it("keeps a newer draft the reader collapsed, after the failed one", async () => {
		const context = fakeContext();
		const { docname } = context;
		let fail: (error: Error) => void = () => {};
		addComment.mockReturnValue(new Promise((_, reject) => (fail = reject)));
		const sent = postComment(context, AUTHOR, DRAFT);
		saveComposerDraft("Note", docname, "comment", { content: "<p>Later</p>", attachments: [] });
		closeComposer();
		fail(new Error("Offline"));
		await sent;
		expect(composerDraft("Note", docname, "comment")).toEqual({
			content: "<p>Looks good</p><p>Later</p>",
			attachments: [FILE],
		});
	});

	it("restores the failed draft alone over an empty writer", async () => {
		const context = fakeContext();
		const { docname } = context;
		let fail: (error: Error) => void = () => {};
		addComment.mockReturnValue(new Promise((_, reject) => (fail = reject)));
		const sent = postComment(context, AUTHOR, DRAFT);
		openComposer("Note", docname, "comment");
		saveComposerDraft("Note", docname, "comment", { content: "<p></p>", attachments: [] });
		fail(new Error("Offline"));
		await sent;
		expect(composerDraft("Note", docname, "comment")).toEqual(DRAFT);
	});

	it("leaves a composer the reader opened on another record since", async () => {
		const context = fakeContext();
		let fail: (error: Error) => void = () => {};
		addComment.mockReturnValue(new Promise((_, reject) => (fail = reject)));
		const sent = postComment(context, AUTHOR, DRAFT);
		openComposer("Note", "ELSEWHERE", "comment");
		fail(new Error("Offline"));
		await sent;
		expect(activeWriter("Note", "ELSEWHERE")).toBe("comment");
		expect(composerDraft("Note", context.docname, "comment")).toEqual(DRAFT);
	});
});
