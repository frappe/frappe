// The field actions the record page hands to a Phone control, over faked app files and a faked dispatcher.
import { beforeEach, describe, expect, it, vi } from "vitest";

const files = vi.hoisted(() => [] as { app: string; load: () => Promise<{ default?: unknown }> }[]);
const found = vi.hoisted(() => new Map<string, { label?: string; icon?: string }>());
const perform = vi.hoisted(() => vi.fn());

vi.mock("@/contributions/registry", () => ({ fieldActionFiles: files }));
vi.mock("@/acts/dispatcher", () => ({ acts: { find: (name: string) => found.get(name), perform } }));

import { FieldActionItems, fieldActions } from "../fieldActions";

const phone = { fieldname: "mobile_no", fieldtype: "Phone" };
const call = { fieldtype: "Phone", act: "shell.crm.make_a_call" };

function shipping(app: string, ...items: unknown[]) {
	files.push({ app, load: async () => ({ default: items }) });
}

async function actionsFor(field: object, value: unknown) {
	const host = fieldActions(new FieldActionItems());
	host.for(field as never, value);
	await new Promise((resolve) => setTimeout(resolve));
	return host.for(field as never, value);
}

beforeEach(() => {
	files.length = 0;
	found.clear();
	perform.mockClear();
	vi.spyOn(console, "warn").mockImplementation(() => {});
});

describe("field actions", () => {
	it("draw none while the item's when(value) is false", async () => {
		shipping("crm", { ...call, when: (value: string) => value.startsWith("+91") });
		found.set("shell.crm.make_a_call", {});

		expect(await actionsFor(phone, "+91 99999 00000")).toHaveLength(1);
		expect(await actionsFor(phone, "99999 00000")).toHaveLength(0);
	});

	it("take the label and icon of the act they place, and run it with the field's value", async () => {
		shipping("crm", call);
		found.set("shell.crm.make_a_call", { label: "Make a call", icon: "lucide-phone" });

		const [action] = await actionsFor(phone, "+91 99999 00000");
		action.run();

		expect(action).toMatchObject({ label: "Make a call", icon: "lucide-phone" });
		expect(perform).toHaveBeenCalledWith("shell.crm.make_a_call", "+91 99999 00000");
	});

	it("let the item set its own label and icon, and map the value the act receives", async () => {
		shipping("crm", { ...call, label: "Call", icon: "lucide-phone-call", value: (v: string) => v.replace(/\s/g, "") });
		found.set("shell.crm.make_a_call", { label: "Make a call", icon: "lucide-phone" });

		const [action] = await actionsFor(phone, "+91 999");
		action.run();

		expect(action).toMatchObject({ label: "Call", icon: "lucide-phone-call" });
		expect(perform).toHaveBeenCalledWith("shell.crm.make_a_call", "+91999");
	});

	it("draw nothing while the act is absent, hidden or denied, which is when the dispatcher does not find it", async () => {
		shipping("crm", call);

		expect(await actionsFor(phone, "123")).toEqual([]);
	});

	it("draw nothing for an empty value", async () => {
		shipping("crm", call);
		found.set("shell.crm.make_a_call", { label: "Make a call" });

		expect(await actionsFor(phone, "")).toEqual([]);
		expect(await actionsFor(phone, "  ")).toEqual([]);
		expect(await actionsFor(phone, null)).toEqual([]);
	});

	it("reach a Data field whose options say Phone, and no other fieldtype", async () => {
		shipping("crm", call);
		found.set("shell.crm.make_a_call", { label: "Make a call" });

		expect(await actionsFor({ fieldname: "n", fieldtype: "Data", options: "Phone" }, "1")).toHaveLength(1);
		expect(await actionsFor({ fieldname: "n", fieldtype: "Data", options: "Email" }, "1")).toEqual([]);
		expect(await actionsFor({ fieldname: "n", fieldtype: "Data" }, "1")).toEqual([]);
	});

	it("keep the apps' order, and ignore an entry with no act or no fieldtype, with a warning", async () => {
		shipping("crm", call, { fieldtype: "Phone" });
		shipping("helpdesk", { fieldtype: "Phone", act: "shell.helpdesk.text" });
		found.set("shell.crm.make_a_call", { label: "Make a call" });
		found.set("shell.helpdesk.text", { label: "Text" });

		const actions = await actionsFor(phone, "1");

		expect(actions.map((action) => action.act)).toEqual(["shell.crm.make_a_call", "shell.helpdesk.text"]);
		expect(console.warn).toHaveBeenCalledWith(expect.stringContaining("crm's field-actions.js holds an entry"));
	});

	it("add nothing from a file that does not load", async () => {
		files.push({ app: "crm", load: () => Promise.reject(new Error("boom")) });
		vi.spyOn(console, "error").mockImplementation(() => {});

		expect(await actionsFor(phone, "1")).toEqual([]);
	});

	it("import nothing when no app ships the file", () => {
		expect(fieldActions(new FieldActionItems()).for(phone as never, "1")).toEqual([]);
	});
});
