// The record host's `postComment`: the live record's writer context, the session's author, the person's draft kept.
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

import { setSession } from "@framework/ui/useSession";
import {
	activeWriter,
	closeComposer,
	composerDraft,
	openComposer,
	registerComposerRecord,
	saveComposerDraft,
} from "@/shell/composer";
import { composerHost } from "../composerHost";

const DRAFT = { content: "<p>Half written</p>", attachments: [] };
const USER = { name: "ann@example.com", full_name: "Ann", email: "ann@example.com", user_image: null };
let unregister: (() => void) | undefined;

function signIn() {
	setSession({ user: { ...USER, document_follow_notify: false }, roles: [], lang: "en", timezone: "UTC", defaults: {} });
}

function openRecord() {
	const firePost = vi.fn(async () => {});
	unregister = registerComposerRecord("Note", "NOTE-H1", {
		doctype: "Note",
		docname: "NOTE-H1",
		title: "NOTE-H1",
		perms: {},
		toast: { error: vi.fn() },
		firePost,
	});
	return firePost;
}

beforeEach(() => {
	vi.clearAllMocks();
	closeComposer();
	signIn();
});
afterEach(() => unregister?.());

describe("composerHost postComment", () => {
	it("posts as the session's user on the open record and keeps the person's draft and writer", async () => {
		const firePost = openRecord();
		openComposer("Note", "NOTE-H1", "comment");
		saveComposerDraft("Note", "NOTE-H1", "comment", DRAFT);
		addComment.mockResolvedValue({ data: { comments: [], added: "C-9" } });

		const name = await composerHost("Note", "NOTE-H1").postComment("<p>Hi</p>");

		expect(name).toBe("C-9");
		expect(addPendingActivity.mock.calls[0][2]).toMatchObject({
			author: { name: USER.name, email: USER.email, fullname: "Ann" },
			data: { content: "<p>Hi</p>" },
		});
		expect(addComment).toHaveBeenCalledWith("Note", "NOTE-H1", "<p>Hi</p>", { attachments: [] });
		expect(firePost).toHaveBeenCalledWith("comment:C-9");
		expect(activeWriter("Note", "NOTE-H1")).toBe("comment");
		expect(composerDraft("Note", "NOTE-H1", "comment")).toEqual(DRAFT);
	});

	it("throws when the record is not open in the tab", async () => {
		await expect(composerHost("Note", "NOTE-H2").postComment("<p>Hi</p>")).rejects.toThrow(
			"This record is not open in the tab"
		);
		expect(addComment).not.toHaveBeenCalled();
	});
});
