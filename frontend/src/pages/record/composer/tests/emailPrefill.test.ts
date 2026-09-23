// What a new email starts with: the record's subject and address, and a reply's headers as desk v1 fills them.
import { describe, expect, it } from "vitest";
import { addressList, asEmailDraft, mergeEmailDrafts } from "../emailDraft";
import { prefillEmail, replyFill } from "../emailPrefill";

const META = {
	fields: [
		{ fieldname: "phone", fieldtype: "Data", options: "Phone" },
		{ fieldname: "email_id", fieldtype: "Data", options: "Email" },
		{ fieldname: "backup_email", fieldtype: "Data", options: "Email" },
	],
};
const ME = "ann@example.com";
const EMAIL = {
	name: "COMM-1",
	subject: "Quote",
	sender: "bob@example.com",
	to: "ann@example.com, carl@example.com",
	cc: "dee@example.com",
	bcc: "eve@example.com",
	content: "<p>Hi</p>",
};

describe("prefillEmail", () => {
	it("answers the record by title, to its first email field", () => {
		const doc = { email_id: "lead@example.com", backup_email: "other@example.com" };
		expect(prefillEmail(META, doc, "Acme deal")).toEqual({
			subject: "Re: Acme deal",
			to: ["lead@example.com"],
		});
	});

	it("leaves To empty when the field is empty or the doctype has none", () => {
		expect(prefillEmail(META, { email_id: "" }, "Acme").to).toEqual([]);
		expect(prefillEmail({ fields: [] }, {}, "Acme").to).toEqual([]);
		expect(prefillEmail(null, {}, "Acme")).toEqual({ subject: "Re: Acme", to: [] });
	});
});

describe("replyFill", () => {
	it("Reply answers the sender alone", () => {
		expect(replyFill(EMAIL, ME, false)).toEqual({
			to: ["bob@example.com"],
			cc: [],
			bcc: [],
			subject: "Re: Quote",
		});
	});

	it("Reply all copies the other recipients and Cc, without the user's own address", () => {
		expect(replyFill(EMAIL, "ANN@example.com", true)).toEqual({
			to: ["bob@example.com"],
			cc: ["carl@example.com", "dee@example.com"],
			bcc: ["eve@example.com"],
			subject: "Re: Quote",
		});
	});

	it("answers the recipients of an email the user sent", () => {
		const mine = { ...EMAIL, sender: ME, to: "bob@example.com" };
		expect(replyFill(mine, ME, false).to).toEqual(["bob@example.com"]);
		expect(replyFill(mine, ME, true)).toMatchObject({
			to: ["bob@example.com"],
			cc: ["dee@example.com"],
			bcc: ["eve@example.com"],
		});
	});

	describe("with named addresses, as a stored email carries them", () => {
		const named = {
			...EMAIL,
			sender: "Bob Stone <bob@example.com>",
			to: '"Ann, Sales" <Ann@Example.com>,  Carl <carl@example.com> ',
			cc: "Dee <dee@example.com>",
			bcc: "Eve <eve@example.com>",
		};
		const sent = {
			...named,
			sender: "Ann <ann@example.com>",
			to: "Bob Stone <bob@example.com>, Carl <carl@example.com>",
			cc: '"Ann, Sales" <ANN@example.com>, Dee <dee@example.com>',
		};

		it("Reply to a received email answers the bare sender", () => {
			expect(replyFill(named, ME, false)).toMatchObject({ to: ["bob@example.com"], cc: [] });
		});

		it("Reply all to a received email copies bare addresses, without the user", () => {
			expect(replyFill(named, ME, true)).toMatchObject({
				to: ["bob@example.com"],
				cc: ["carl@example.com", "dee@example.com"],
				bcc: ["eve@example.com"],
			});
		});

		it("Reply to a sent email answers its recipients, not the user", () => {
			expect(replyFill(sent, ME, false).to).toEqual(["bob@example.com", "carl@example.com"]);
		});

		it("Reply all to a sent email copies Cc without the user", () => {
			expect(replyFill(sent, ME, true)).toMatchObject({
				to: ["bob@example.com", "carl@example.com"],
				cc: ["dee@example.com"],
			});
		});
	});

	it("adds no second Re:", () => {
		expect(replyFill({ ...EMAIL, subject: "RE: Quote" }, ME, false).subject).toBe("RE: Quote");
		expect(replyFill({ ...EMAIL, subject: "Re:Quote" }, ME, false).subject).toBe("Re:Quote");
	});
});

describe("the draft's addresses", () => {
	it("reads a comma-separated string or a list, trimmed, with no blanks or repeats", () => {
		expect(addressList(" a@example.com, ,b@example.com,A@example.com ")).toEqual([
			"a@example.com",
			"b@example.com",
		]);
		expect(addressList(["a@example.com", 3, " c@example.com"])).toEqual([
			"a@example.com",
			"c@example.com",
		]);
		expect(asEmailDraft({ to: "a@example.com", cc: undefined }).cc).toEqual([]);
	});

	it("reads a named address as the bare one, a comma in a quoted name kept whole", () => {
		const text = ' "Doe, Jo" < jo@example.com >, Bob <bob@example.com>,bob@example.com ';
		expect(addressList(text)).toEqual(["jo@example.com", "bob@example.com"]);
		expect(asEmailDraft({ cc: ["Dee <dee@example.com>"] }).cc).toEqual(["dee@example.com"]);
	});

	it("merges a failed draft before a newer one, the newer keeping its headers", () => {
		const failed = asEmailDraft({
			to: ["a@example.com"],
			subject: "Old",
			content: "<p>First</p>",
			inReplyTo: "COMM-1",
		});
		const current = asEmailDraft({
			to: ["b@example.com", "a@example.com"],
			subject: "New",
			content: "<p>Second</p>",
		});
		expect(mergeEmailDrafts(failed, current)).toMatchObject({
			to: ["a@example.com", "b@example.com"],
			subject: "New",
			content: "<p>First</p><p>Second</p>",
			inReplyTo: "COMM-1",
		});
	});
});
