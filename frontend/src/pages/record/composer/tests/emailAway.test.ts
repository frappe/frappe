// A list row's email button opens the email writer floating on a record whose page is not mounted.
import { describe, expect, it } from "vitest";
import { keepRecordAway } from "@/shell/composer";
import {
	closeComposer,
	composerDraft,
	composerKept,
	composerState,
	draftRevision,
	replaceComposerDraft,
	clearComposerDraft,
} from "@/shell/composer";
import { EMAIL_WRITER, readEmailDraft } from "../emailDraft";
import { addRecipients, openEmailAway } from "../emailSeed";
import { openWriterItems } from "../writerContext";

describe("openEmailAway", () => {
	it("opens the email writer floating, addressed to the address, with the email writer on offer", () => {
		openEmailAway("Lead", "L-away", ["a@x.com"], { email: true, write: false });

		expect(composerState).toMatchObject({ doctype: "Lead", name: "L-away", active: "email", window: "floating" });
		expect(readEmailDraft("Lead", "L-away").to).toEqual(["a@x.com"]);
		expect(composerKept().perms).toEqual({ email: true, write: false });
		expect(openWriterItems().map((writer) => writer.name)).toContain("email");

		closeComposer();
		clearComposerDraft("Lead", "L-away", EMAIL_WRITER);
		expect(composerDraft("Lead", "L-away", EMAIL_WRITER)).toBeUndefined();
	});

	it("leaves what a visit to the record's page kept", () => {
		keepRecordAway("Lead", "L-kept", { title: "Ada", perms: { email: true, write: true } });
		openEmailAway("Lead", "L-kept", ["a@x.com"], { email: true });

		expect(composerKept()).toEqual({ title: "Ada", perms: { email: true, write: true } });

		closeComposer();
		clearComposerDraft("Lead", "L-kept", EMAIL_WRITER);
	});

	it("adds the address to the To of an unsent draft and keeps the rest of it", () => {
		replaceComposerDraft("Lead", "L-draft", EMAIL_WRITER, { to: ["b@x.com"], subject: "Hi", content: "Body" });
		openEmailAway("Lead", "L-draft", ["a@x.com"], { email: true });

		expect(readEmailDraft("Lead", "L-draft")).toMatchObject({
			to: ["b@x.com", "a@x.com"],
			subject: "Hi",
			content: "Body",
		});

		closeComposer();
		clearComposerDraft("Lead", "L-draft", EMAIL_WRITER);
	});

	it("does not add an address the draft has, whatever its case", () => {
		replaceComposerDraft("Lead", "L-same", EMAIL_WRITER, { to: ["A@x.com"], subject: "Hi" });
		addRecipients("Lead", "L-same", ["a@x.com", "c@x.com"]);

		expect(readEmailDraft("Lead", "L-same").to).toEqual(["A@x.com", "c@x.com"]);

		clearComposerDraft("Lead", "L-same", EMAIL_WRITER);
	});

	it("adds an address once, though the value lists it twice, and redraws the open writer only for a change", () => {
		replaceComposerDraft("Lead", "L-dup", EMAIL_WRITER, { to: ["b@x.com"], subject: "Hi" });
		const before = draftRevision("Lead", "L-dup", EMAIL_WRITER);
		addRecipients("Lead", "L-dup", ["a@x.com", "A@x.com"]);
		expect(readEmailDraft("Lead", "L-dup").to).toEqual(["b@x.com", "a@x.com"]);
		expect(draftRevision("Lead", "L-dup", EMAIL_WRITER)).toBe(before + 1);
		addRecipients("Lead", "L-dup", ["B@x.com"]);
		expect(draftRevision("Lead", "L-dup", EMAIL_WRITER)).toBe(before + 1);

		clearComposerDraft("Lead", "L-dup", EMAIL_WRITER);
	});

	it("stores nothing when the record holds no draft", () => {
		addRecipients("Lead", "L-none", ["a@x.com"]);
		expect(composerDraft("Lead", "L-none", EMAIL_WRITER)).toBeUndefined();
	});
});
