// How the email writer opens: the prefill, a script's draft over it, a reply, and a stored draft re-addressed.
import { beforeEach, describe, expect, it, vi } from "vitest";

const { activityTimelineRows } = vi.hoisted(() => ({
	activityTimelineRows: vi.fn((..._args: unknown[]): unknown[] => []),
}));
vi.mock("@framework/ui/ActivityTimeline", async (importOriginal) => ({
	...((await importOriginal()) as object),
	activityTimelineRows,
}));

import {
	activeWriter,
	closeComposer,
	composerDraft,
	draftRevision,
	saveComposerDraft,
} from "@/shell/composer";
import { composerBuiltins, composerHost } from "../composerHost";
import { asEmailDraft } from "../emailDraft";
import { freshEmail } from "../emailSeed";

const ME = "ann@example.com";
const META = {
	title_field: "lead_name",
	fields: [{ fieldname: "email_id", fieldtype: "Data", options: "Email" }],
};
const EMAIL = {
	type: "email",
	key: "email:COMM-1",
	data: {
		name: "COMM-1",
		subject: "Quote",
		sender: "bob@example.com",
		to: "ann@example.com, carl@example.com",
		cc: "",
		bcc: "eve@example.com",
		content: "<p>Hi</p>",
	},
};

let record = 0;

function fakePage(items: unknown[] = []) {
	const docname = `LEAD-${++record}`;
	return {
		doctype: "Lead",
		docname,
		meta: META,
		doc: { lead_name: "Acme", email_id: "lead@example.com" },
		activity: { items },
	} as any;
}

function open(page: any, draft?: Record<string, unknown>) {
	const host = composerHost(page.doctype, page.docname, { page: () => page, userEmail: ME });
	host.openWriter("email", { draft });
}

const stored = (page: any) => composerDraft("Lead", page.docname, "email");

beforeEach(() => {
	vi.clearAllMocks();
	closeComposer();
});

describe("a new email", () => {
	it("opens on the record's title and address, and keeps nothing for an untouched open", () => {
		const page = fakePage();
		open(page);
		expect(activeWriter("Lead", page.docname)).toBe("email");
		expect(stored(page)).toBeUndefined();
		expect(freshEmail(page)).toEqual(
			asEmailDraft({ subject: "Re: Acme", to: ["lead@example.com"] })
		);
	});

	it("takes a script's draft after an untouched open", () => {
		const page = fakePage();
		open(page);
		open(page, { subject: "Script's" });
		expect(stored(page)).toMatchObject({ subject: "Script's", to: ["lead@example.com"] });
	});

	it("keeps a script's sender, though it alone leaves the draft fresh", () => {
		const page = fakePage();
		open(page, { from: "sales@example.com" });
		expect(stored(page)).toMatchObject({ from: "sales@example.com", subject: "Re: Acme" });
	});

	it("takes a script's draft over the prefill, addresses as a string or a list", () => {
		const page = fakePage();
		open(page, { to: "x@example.com, y@example.com", cc: ["z@example.com"], content: "<p>Hi</p>" });
		expect(stored(page)).toMatchObject({
			subject: "Re: Acme",
			to: ["x@example.com", "y@example.com"],
			cc: ["z@example.com"],
			content: "<p>Hi</p>",
		});
	});

	it("keeps a draft already in memory over both", () => {
		const page = fakePage();
		saveComposerDraft("Lead", page.docname, "email", asEmailDraft({ subject: "Mine" }));
		open(page, { subject: "Script's" });
		expect(stored(page)).toMatchObject({ subject: "Mine", to: [] });
	});

	it("uses the record's name when it has no title", () => {
		const page = fakePage();
		page.doc = {};
		expect(freshEmail(page).subject).toBe(`Re: ${page.docname}`);
	});
});

describe("a reply", () => {
	it("fills Reply from an email the Activity tab holds", () => {
		const page = fakePage([{ ...EMAIL, name: EMAIL.key }]);
		open(page, { replyTo: "email:COMM-1" });
		expect(stored(page)).toMatchObject({
			to: ["bob@example.com"],
			cc: [],
			bcc: [],
			subject: "Re: Quote",
			inReplyTo: "COMM-1",
		});
	});

	it("fills Reply all from an email only the Emails tab holds", () => {
		const page = fakePage();
		activityTimelineRows.mockReturnValue([EMAIL]);
		open(page, { replyTo: "email:COMM-1", replyAll: true });
		expect(activityTimelineRows).toHaveBeenCalledWith("Lead", page.docname, ["email"]);
		expect(stored(page)).toMatchObject({
			to: ["bob@example.com"],
			cc: ["carl@example.com"],
			bcc: ["eve@example.com"],
		});
	});

	it("threads an email just sent, whose row carries the key but no name", () => {
		const page = fakePage();
		const sent = { ...EMAIL.data, name: "", sender: ME, to: "bob@example.com" };
		activityTimelineRows.mockReturnValue([{ ...EMAIL, key: "email:COMM-7", data: sent }]);
		open(page, { replyTo: "email:COMM-7" });
		expect(stored(page)).toMatchObject({ to: ["bob@example.com"], inReplyTo: "COMM-7" });
	});

	it("still threads an email the reader has not loaded", () => {
		const page = fakePage();
		open(page, { replyTo: "email:COMM-9" });
		expect(stored(page)).toMatchObject({
			to: ["lead@example.com"],
			subject: "Re: Acme",
			inReplyTo: "COMM-9",
		});
	});
});

describe("the quote under a reply", () => {
	const ON = "On 20th September 2026, 10:00 AM, bob@example.com wrote:";
	const loaded = (data: Record<string, unknown> = {}) => ({
		...EMAIL,
		name: EMAIL.key,
		timestamp: "2026-09-20 10:00:00",
		data: { ...EMAIL.data, ...data },
	});

	it("quotes the email Reply answers as desk v1 does, an On … wrote: line over its text", () => {
		const page = fakePage([loaded({ content: "<p>One</p><div>Two</div>" })]);
		open(page, { replyTo: "email:COMM-1" });
		expect(stored(page)!.quoted).toBe(`<p>${ON}</p><p>One<br>Two</p>`);
	});

	it("quotes on Reply all too, from an email only the Emails tab holds", () => {
		const page = fakePage();
		activityTimelineRows.mockReturnValue([{ ...EMAIL, timestamp: "2026-09-20 10:00:00" }]);
		open(page, { replyTo: "email:COMM-1", replyAll: true });
		expect(stored(page)!.quoted).toBe(`<p>${ON}</p><p>Hi</p>`);
	});

	it("names only the sender of an email just sent, which has no time yet", () => {
		const page = fakePage();
		activityTimelineRows.mockReturnValue([EMAIL]);
		open(page, { replyTo: "email:COMM-1" });
		expect(stored(page)!.quoted).toBe("<p>bob@example.com wrote:</p><p>Hi</p>");
	});

	it("clips the text at desk v1's 20 KiB", () => {
		const page = fakePage([loaded({ content: `<p>${"a".repeat(30000)}</p>` })]);
		open(page, { replyTo: "email:COMM-1" });
		expect(stored(page)!.quoted).toBe(`<p>${ON}</p><p>${"a".repeat(20 * 1024)}</p>`);
	});

	it("keeps the email's markup out, as text", () => {
		const html =
			`<style>p{color:red}</style><p><b>Bold</b> <img src="x" onerror="alert(1)">` +
			`<script>alert(2)</script>&lt;i&gt;</p>`;
		const page = fakePage([loaded({ content: html })]);
		open(page, { replyTo: "email:COMM-1" });
		expect(stored(page)!.quoted).toBe(`<p>${ON}</p><p>Bold &lt;i&gt;</p>`);
	});

	it("is not there on a plain open, or for an email the reader has not loaded", () => {
		const page = fakePage([loaded()]);
		open(page, { subject: "From a script" });
		expect(stored(page)!.quoted).toBe("");
		const other = fakePage();
		open(other, { replyTo: "email:COMM-9" });
		expect(stored(other)!.quoted).toBe("");
	});

	it("is replaced by a reply over a draft in memory, and dropped for one not loaded", () => {
		const page = fakePage([
			loaded(),
			{ ...loaded({ content: "<p>Later</p>" }), name: "email:COMM-2" },
		]);
		const draft = asEmailDraft({ content: "<p>Kept</p>", quoted: "<p>Old quote</p>" });
		saveComposerDraft("Lead", page.docname, "email", draft);
		open(page, { replyTo: "email:COMM-2" });
		expect(stored(page)).toMatchObject({
			content: "<p>Kept</p>",
			quoted: `<p>${ON}</p><p>Later</p>`,
		});
		open(page, { replyTo: "email:COMM-9" });
		expect(stored(page)).toMatchObject({ content: "<p>Kept</p>", quoted: "" });
	});
});

describe("a reply over a draft in memory", () => {
	const body = { content: "<p>Kept</p>", attachments: [{ name: "F-1" }] };

	it("re-addresses it, keeps the body and attachments, and redraws the writer", () => {
		const page = fakePage([{ ...EMAIL, name: EMAIL.key }]);
		const draft = asEmailDraft({ to: "old@example.com", bcc: "me@example.com", subject: "Old", ...body });
		saveComposerDraft("Lead", page.docname, "email", draft);
		const revision = draftRevision("Lead", page.docname, "email");
		open(page, { replyTo: "email:COMM-1", subject: "ignored" });
		expect(stored(page)).toMatchObject({
			to: ["bob@example.com"],
			cc: [],
			bcc: ["me@example.com"],
			subject: "Re: Quote",
			inReplyTo: "COMM-1",
			...body,
		});
		expect(draftRevision("Lead", page.docname, "email")).toBe(revision + 1);
	});

	it("takes the original Bcc on a Reply all", () => {
		const page = fakePage([{ ...EMAIL, name: EMAIL.key }]);
		saveComposerDraft("Lead", page.docname, "email", asEmailDraft({ bcc: "me@example.com" }));
		open(page, { replyTo: "email:COMM-1", replyAll: true });
		expect(stored(page)!.bcc).toEqual(["eve@example.com"]);
	});

	it("leaves it alone without a replyTo", () => {
		const page = fakePage();
		saveComposerDraft("Lead", page.docname, "email", asEmailDraft({ to: "old@example.com" }));
		const revision = draftRevision("Lead", page.docname, "email");
		open(page, { to: "new@example.com" });
		expect(stored(page)!.to).toEqual(["old@example.com"]);
		expect(draftRevision("Lead", page.docname, "email")).toBe(revision);
	});
});

describe("composerBuiltins", () => {
	it("lists the email writer after comment only with the email right", () => {
		expect(composerBuiltins({ email: 1 }).map((item) => item.name)).toEqual(["comment", "email"]);
		expect(composerBuiltins({ email: 0 }).map((item) => item.name)).toEqual(["comment"]);
		expect(composerBuiltins().map((item) => item.name)).toEqual(["comment"]);
	});
});
