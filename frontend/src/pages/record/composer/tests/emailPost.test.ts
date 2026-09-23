// The email send: a pending row at once, the server's key on it, onPost, and the draft back on a failure.
import { beforeEach, describe, expect, it, vi } from "vitest";

const { runMethod, pending, addPendingActivity } = vi.hoisted(() => {
	const pending = { resolve: vi.fn(), drop: vi.fn() };
	return {
		runMethod: vi.fn(),
		pending,
		addPendingActivity: vi.fn((..._args: unknown[]) => pending),
	};
});
vi.mock("@framework/ui/api", () => ({ runMethod }));
vi.mock("@framework/ui/ActivityTimeline", () => ({ addPendingActivity }));

import {
	activeWriter,
	closeComposer,
	composerDraft,
	draftRevision,
	openComposer,
	saveComposerDraft,
} from "@/shell/composer";
import { asEmailDraft } from "../emailDraft";
import { postEmail } from "../emailPost";

const AUTHOR = { name: "ann@example.com", email: "ann@example.com", fullname: "Ann" };
const FILE = {
	name: "F-9",
	file_name: "quote.pdf",
	file_url: "/private/files/quote.pdf",
	file_type: "application/pdf",
};
const DRAFT = asEmailDraft({
	from: "sales@example.com",
	to: ["bob@example.com", "carl@example.com"],
	cc: ["dee@example.com"],
	subject: "Re: Acme",
	content: "<p>Attached</p>",
	attachments: [FILE],
	inReplyTo: "COMM-1",
});

let record = 0;

function fakeContext() {
	const docname = `LEAD-${++record}`;
	return {
		doctype: "Lead",
		docname,
		title: docname,
		perms: {},
		toast: { error: vi.fn(), success: vi.fn() },
		firePost: vi.fn(async () => {}),
	};
}

beforeEach(() => {
	vi.clearAllMocks();
	closeComposer();
});

describe("postEmail", () => {
	it("collapses, clears the draft and adds a pending email row before the answer", () => {
		const context = fakeContext();
		const { docname } = context;
		openComposer("Lead", docname, "email");
		saveComposerDraft("Lead", docname, "email", DRAFT);
		runMethod.mockReturnValue(new Promise(() => {}));
		void postEmail(context, AUTHOR, DRAFT, DRAFT.content);
		expect(activeWriter("Lead", docname)).toBe("");
		expect(composerDraft("Lead", docname, "email")).toBeUndefined();
		expect(addPendingActivity).toHaveBeenCalledWith("Lead", docname, {
			type: "email",
			author: AUTHOR,
			data: {
				name: "",
				subject: "Re: Acme",
				sender: "sales@example.com",
				to: "bob@example.com, carl@example.com",
				cc: "dee@example.com",
				bcc: "",
				content: "<p>Attached</p>",
				attachments: [{ file_url: FILE.file_url, file_name: FILE.file_name, is_private: 1 }],
			},
		});
	});

	it("leaves open a comment writer the reader moved to on the same record", () => {
		const context = fakeContext();
		const { docname } = context;
		openComposer("Lead", docname, "comment");
		runMethod.mockReturnValue(new Promise(() => {}));
		void postEmail(context, AUTHOR, DRAFT, DRAFT.content);
		expect(activeWriter("Lead", docname)).toBe("comment");
		expect(addPendingActivity).toHaveBeenCalled();
	});

	it("sends every field make takes, and lets the server pick a missing sender", async () => {
		const context = fakeContext();
		runMethod.mockResolvedValue({ data: { name: "COMM-2" } });
		await postEmail(context, AUTHOR, DRAFT, DRAFT.content);
		expect(runMethod).toHaveBeenCalledWith("frappe.core.doctype.communication.email.make", {
			doctype: "Lead",
			name: context.docname,
			content: "<p>Attached</p>",
			subject: "Re: Acme",
			recipients: "bob@example.com, carl@example.com",
			cc: "dee@example.com",
			bcc: "",
			sender: "sales@example.com",
			sender_full_name: "Ann",
			send_email: 1,
			attachments: ["F-9"],
			in_reply_to: "COMM-1",
		});
		await postEmail(context, AUTHOR, { ...DRAFT, from: "", inReplyTo: "" }, DRAFT.content);
		const args = runMethod.mock.calls[1][1];
		expect(args.sender).toBeUndefined();
		expect(args.in_reply_to).toBeUndefined();
		expect((addPendingActivity.mock.calls[1][2] as any).data.sender).toBe("ann@example.com");
	});

	it("sends and shows the quoted message, and restores the body and quote apart", async () => {
		const context = fakeContext();
		const { docname } = context;
		const draft = { ...DRAFT, quoted: "<p>On it, bob wrote:</p><p>Hi</p>" };
		const message = `<p>Attached</p><p class="reply-to-content"></p><blockquote>${draft.quoted}</blockquote>`;
		runMethod.mockRejectedValue(new Error("Offline"));
		await postEmail(context, AUTHOR, draft, message);
		expect(runMethod.mock.calls[0][1].content).toBe(message);
		expect((addPendingActivity.mock.calls[0][2] as any).data.content).toBe(message);
		expect(composerDraft("Lead", docname, "email")).toEqual(draft);
	});

	it("gives the row its server key, with no time, then fires onPost with the key", async () => {
		const context = fakeContext();
		runMethod.mockResolvedValue({ data: { name: "COMM-2", emails_not_sent_to: "" } });
		await postEmail(context, AUTHOR, DRAFT, DRAFT.content);
		expect(pending.resolve).toHaveBeenCalledWith("email:COMM-2");
		expect(context.firePost).toHaveBeenCalledWith("email:COMM-2");
		expect(pending.drop).not.toHaveBeenCalled();
	});

	it("takes the row back, restores the draft, reopens and says why on a failure", async () => {
		const context = fakeContext();
		const { docname } = context;
		runMethod.mockRejectedValue(new Error("No outgoing account"));
		await postEmail(context, AUTHOR, DRAFT, DRAFT.content);
		expect(pending.drop).toHaveBeenCalled();
		expect(context.firePost).not.toHaveBeenCalled();
		expect(composerDraft("Lead", docname, "email")).toEqual(DRAFT);
		expect(activeWriter("Lead", docname)).toBe("email");
		expect(context.toast.error).toHaveBeenCalledWith("No outgoing account");
	});

	it("puts the failed body before a newer draft's, and redraws the writer", async () => {
		const context = fakeContext();
		const { docname } = context;
		let fail: (error: Error) => void = () => {};
		runMethod.mockReturnValue(new Promise((_, reject) => (fail = reject)));
		const sent = postEmail(context, AUTHOR, DRAFT, DRAFT.content);
		openComposer("Lead", docname, "email");
		const newer = asEmailDraft({ subject: "Other", content: "<p>Later</p>", to: "eve@example.com" });
		saveComposerDraft("Lead", docname, "email", newer);
		const revision = draftRevision("Lead", docname, "email");
		fail(new Error("Offline"));
		await sent;
		expect(composerDraft("Lead", docname, "email")).toMatchObject({
			to: ["bob@example.com", "carl@example.com", "eve@example.com"],
			subject: "Other",
			content: "<p>Attached</p><p>Later</p>",
			attachments: [FILE],
		});
		expect(draftRevision("Lead", docname, "email")).toBe(revision + 1);
	});

	it("restores the failed draft whole over a reopened writer with only a prefill", async () => {
		const context = fakeContext();
		const { docname } = context;
		let fail: (error: Error) => void = () => {};
		runMethod.mockReturnValue(new Promise((_, reject) => (fail = reject)));
		const sent = postEmail(context, AUTHOR, DRAFT, DRAFT.content);
		openComposer("Lead", docname, "email", asEmailDraft({ subject: "Re: Lead", content: "<p></p>" }));
		fail(new Error("Offline"));
		await sent;
		expect(composerDraft("Lead", docname, "email")).toEqual(DRAFT);
	});
});
