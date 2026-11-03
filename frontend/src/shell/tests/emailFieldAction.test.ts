// The shell's email button on a Data field with options Email: shown for a value and the email right,
// hidden without either, and it opens the composer with the address as the recipient.
import { beforeEach, describe, expect, it, vi } from "vitest";

const holds = vi.hoisted(() => ({ email: true, write: true }));
const context = vi.hoisted(() => ({ value: null as null | { page?: unknown; perms: Record<string, unknown>; writers?: { name: string }[] } }));
const away = vi.hoisted(() => vi.fn());
const add = vi.hoisted(() => vi.fn());
const openers = { openAway: away, addRecipients: add };

vi.mock("@/acts/doctypeRight", () => ({
	doctypeRight: { passes: ({ ptype }: { ptype: "email" }) => holds[ptype] },
}));
vi.mock("@framework/ui/useDocPermissions", () => ({
	useDocPermissions: () => ({ holds: (right: "write") => holds[right] }),
}));
const kept = vi.hoisted(() => ({ writers: undefined as undefined | { name: string }[] }));
vi.mock("../composer", () => ({ composerRecordFor: () => context.value, keptWriters: () => kept.writers }));

import { emailFieldAction } from "../emailFieldAction";

const email = { fieldname: "email_id", fieldtype: "Data", options: "Email" };
const onRecord = { doctype: "Lead", name: "L1", surface: "record" as const };
const inList = { ...onRecord, surface: "list" as const };
const open = vi.fn();

beforeEach(() => {
	holds.email = true;
	holds.write = true;
	open.mockClear();
	away.mockClear();
	add.mockClear();
	kept.writers = undefined;
	context.value = { page: { composer: { open } }, perms: { email: 1 }, writers: [{ name: "comment" }, { name: "email" }] };
});

describe("the email field action", () => {
	it("is one lucide-mail button for an Email field", () => {
		expect(emailFieldAction(email, "a@x.com", onRecord, openers)).toMatchObject([
			{ label: "Email", icon: "lucide-mail" },
		]);
	});

	it("draws nothing for another field, another Data option or no record", () => {
		expect(emailFieldAction({ fieldname: "n", fieldtype: "Data" }, "a@x.com", onRecord, openers)).toEqual([]);
		expect(emailFieldAction({ fieldname: "n", fieldtype: "Data", options: "Phone" }, "a@x.com", onRecord, openers)).toEqual([]);
		expect(emailFieldAction(email, "a@x.com", undefined, openers)).toEqual([]);
	});

	it("draws nothing without the email right on the doctype", () => {
		holds.email = false;
		expect(emailFieldAction(email, "a@x.com", onRecord, openers)).toEqual([]);
		expect(emailFieldAction(email, "a@x.com", inList, openers)).toEqual([]);
	});

	it("draws nothing on a record page that is not live or has no email right on the record", () => {
		context.value = { page: { composer: { open } }, perms: {}, writers: [{ name: "email" }] };
		expect(emailFieldAction(email, "a@x.com", onRecord, openers)).toEqual([]);
		context.value = null;
		expect(emailFieldAction(email, "a@x.com", onRecord, openers)).toEqual([]);
	});

	it("opens the record's email writer with the address as the recipient", () => {
		emailFieldAction(email, "a@x.com", onRecord, openers)[0].run();
		expect(open).toHaveBeenCalledWith("email", { draft: { to: ["a@x.com"] } });
		expect(away).not.toHaveBeenCalled();
	});

	it("opens the row's record floating from a list, though its page is not loaded", () => {
		context.value = null;
		emailFieldAction(email, "a@x.com", inList, openers)[0].run();
		expect(away).toHaveBeenCalledWith("Lead", "L1", ["a@x.com"], { email: true, write: true });
	});

	it("draws nothing for a value that is not an address, or has one bad part", () => {
		for (const value of ["", "  ", "not an address", "a@x", "a@x.com, junk", "Ada <a@x.com>"])
			expect(emailFieldAction(email, value, onRecord, openers)).toEqual([]);
		expect(emailFieldAction(email, "nope", inList, openers)).toEqual([]);
	});

	it("takes every address of a comma or semicolon list", () => {
		emailFieldAction(email, " a@x.com; b@x.com ,c@x.com", onRecord, openers)[0].run();
		expect(open).toHaveBeenCalledWith("email", { draft: { to: ["a@x.com", "b@x.com", "c@x.com"] } });
	});

	it("adds the address to a draft the record already holds before it opens", () => {
		emailFieldAction(email, "a@x.com", onRecord, openers)[0].run();
		expect(add).toHaveBeenCalledWith("Lead", "L1", ["a@x.com"]);
		expect(add.mock.invocationCallOrder[0]).toBeLessThan(open.mock.invocationCallOrder[0]);
		context.value = null;
		emailFieldAction(email, "a@x.com", inList, openers)[0].run();
		expect(add).toHaveBeenCalledTimes(1);
	});

	it("draws nothing in a list for a record whose visited page hid the email writer", () => {
		context.value = null;
		kept.writers = [{ name: "comment" }];
		expect(emailFieldAction(email, "a@x.com", inList, openers)).toEqual([]);
		kept.writers = [{ name: "comment" }, { name: "email" }];
		expect(emailFieldAction(email, "a@x.com", inList, openers)).toHaveLength(1);
	});

	it("draws nothing on a record page where a script hid the email writer", () => {
		context.value = { page: { composer: { open } }, perms: { email: 1 }, writers: [{ name: "comment" }] };
		expect(emailFieldAction(email, "a@x.com", onRecord, openers)).toEqual([]);
	});
});
