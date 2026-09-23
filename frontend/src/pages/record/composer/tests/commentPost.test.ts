// The comment send: a pending row at once, the server's key and time on it, and the draft back on a failure.
import { beforeEach, describe, expect, it, vi } from "vitest";

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
	openComposer,
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

function fakeController() {
	const docname = `NOTE-${++record}`;
	return {
		page: {
			doctype: "Note",
			docname,
			toast: { error: vi.fn(), success: vi.fn() },
		},
		firePost: vi.fn(async () => {}),
	} as any;
}

function opened(controller: any) {
	openComposer("Note", controller.page.docname, "comment");
	saveComposerDraft("Note", controller.page.docname, "comment", DRAFT);
}

beforeEach(() => {
	vi.clearAllMocks();
	closeComposer();
});

describe("postComment", () => {
	it("collapses, clears the draft and adds a pending row in the reader's name before the answer", async () => {
		const controller = fakeController();
		opened(controller);
		addComment.mockReturnValue(new Promise(() => {}));
		void postComment(controller, AUTHOR, DRAFT);
		expect(activeWriter("Note", controller.page.docname)).toBe("");
		expect(composerDraft("Note", controller.page.docname, "comment")).toBeUndefined();
		expect(addPendingActivity).toHaveBeenCalledWith("Note", controller.page.docname, {
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
		expect(addComment).toHaveBeenCalledWith("Note", controller.page.docname, DRAFT.content, {
			attachments: ["F-9"],
		});
	});

	it("gives the row its server key and time, then fires onPost with the key", async () => {
		const controller = fakeController();
		addComment.mockResolvedValue({
			data: {
				comments: [
					{ name: "C-1", creation: "2026-09-01 10:00:00" },
					{ name: "C-2", creation: "2026-09-23 12:00:00" },
				],
				added: "C-2",
			},
		});
		await postComment(controller, AUTHOR, DRAFT);
		expect(pending.resolve).toHaveBeenCalledWith("comment:C-2", "2026-09-23 12:00:00");
		expect(controller.firePost).toHaveBeenCalledWith("comment:C-2");
		expect(pending.drop).not.toHaveBeenCalled();
	});

	it("takes the row back, restores the draft, reopens and says why on a failure", async () => {
		const controller = fakeController();
		opened(controller);
		addComment.mockRejectedValue(new Error("Not permitted"));
		await postComment(controller, AUTHOR, DRAFT);
		expect(pending.drop).toHaveBeenCalled();
		expect(pending.resolve).not.toHaveBeenCalled();
		expect(controller.firePost).not.toHaveBeenCalled();
		expect(composerDraft("Note", controller.page.docname, "comment")).toEqual(DRAFT);
		expect(activeWriter("Note", controller.page.docname)).toBe("comment");
		expect(controller.page.toast.error).toHaveBeenCalledWith("Not permitted");
	});

	it("leaves a composer the reader opened on another record since", async () => {
		const controller = fakeController();
		let fail: (error: Error) => void = () => {};
		addComment.mockReturnValue(new Promise((_, reject) => (fail = reject)));
		const sent = postComment(controller, AUTHOR, DRAFT);
		openComposer("Note", "ELSEWHERE", "comment");
		fail(new Error("Offline"));
		await sent;
		expect(activeWriter("Note", "ELSEWHERE")).toBe("comment");
		expect(composerDraft("Note", controller.page.docname, "comment")).toEqual(DRAFT);
	});
});
