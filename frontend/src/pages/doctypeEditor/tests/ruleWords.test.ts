import { afterEach, describe, expect, it, vi } from "vitest";

const { toast } = vi.hoisted(() => ({ toast: { error: vi.fn(), success: vi.fn() } }));
vi.mock("frappe-ui", async (importOriginal) => ({
	...(await importOriginal<typeof import("frappe-ui")>()),
	toast,
}));

import { containerRules, FIELD_RULES, ruleValue } from "../ruleRows";
import { acts } from "@/acts/dispatcher";
import { RuleWords } from "../ruleWords";
import { mountEditor, taskNote } from "./editorFixture";

let stop: (() => void) | undefined;
afterEach(() => {
	stop?.();
	stop = undefined;
});

function mount(...args: Parameters<typeof taskNote>) {
	const mounted = mountEditor(taskNote(...args));
	stop = mounted.stop;
	return { canvas: mounted.canvas, said: RuleWords.of(mounted.canvas) };
}

function words(...args: Parameters<typeof taskNote>) {
	return mount(...args).said;
}

describe("a field's rule rows, in words", () => {
	it("says a readable rule as one line, with the row's label in its sentence", () => {
		const said = words();
		expect(said.say("eval:doc.status=='Open'", "Always")).toEqual({ kind: "rules", text: "Status is Open" });
		expect(said.sentence(rule("depends_on"), "eval:doc.status=='Open'")).toBe("Visible if Status is Open");
	});

	it("says each row's empty word, and no sentence for an empty rule", () => {
		const said = words();
		expect(FIELD_RULES.map((one) => said.say("", one.empty).text)).toEqual(["Always", "Never", "Never"]);
		expect(said.sentence(rule("mandatory_depends_on"), "")).toBe("");
	});

	it("keeps a rule the builder cannot read as its code, and says so in the sentence", () => {
		const said = words();
		const raw = "eval:frappe.user.has_role('Accounts User')";
		expect(said.say(raw, "Always")).toEqual({ kind: "code", text: "frappe.user.has_role('Accounts User')" });
		expect(said.sentence(rule("read_only_depends_on"), raw)).toBe(
			"Read-only if (code): frappe.user.has_role('Accounts User')",
		);
	});

	it("says checks, tables, the record's own fields, field comparisons and groups", () => {
		const said = words({
			definition: {
				name: "Task Note",
				is_submittable: 1,
				fields: [
					{ fieldname: "status", label: "Status", fieldtype: "Select", options: "Open\nDone" },
					{ fieldname: "urgent", label: "Urgent", fieldtype: "Check" },
					{ fieldname: "steps", label: "Steps", fieldtype: "Table", options: "Task Step" },
					{ fieldname: "owner_name", label: "Owner", fieldtype: "Data" },
					{ fieldname: "assignee", label: "Assignee", fieldtype: "Data" },
				],
			},
		});
		const text = (raw: string) => said.say(raw, "Always").text;
		expect(text("eval:doc.urgent")).toBe("Urgent is on");
		expect(text("eval:!doc.urgent")).toBe("Urgent is off");
		expect(text("eval:doc.steps.length > 0")).toBe("Steps has rows");
		expect(text("eval:doc.__islocal")).toBe("Record is new");
		expect(text("eval:doc.docstatus == 1")).toBe("Document status is Submitted");
		expect(text("eval:doc.owner_name === doc.assignee")).toBe("Owner is the same as Assignee");
		expect(text('eval:in_list(["Open", "Done"], doc.status)')).toBe("Status is one of Open, Done");
		expect(text('eval:doc.urgent && (doc.status == "Open" || !doc.assignee)')).toBe(
			"Urgent is on and (Status is Open or Assignee is empty)",
		);
		expect(text("owner_name")).toBe("Owner is set");
	});
});

describe("a container's rule rows, in words", () => {
	it("gives a section Visible if, and Starts open if only while it is collapsible", async () => {
		const { canvas, said } = mount();
		const section = () => canvas.tabs.value[0].sections[1];
		const lines = () =>
			containerRules("section", section()).map((one) => [one.label, said.say(ruleValue(section(), one), one.empty).text]);
		expect(lines()).toEqual([["Visible if", "Status is set"]]);
		await acts.run("canvas.set_container_property", { container: "more", property: "collapsible", value: true });
		expect(lines()).toEqual([
			["Visible if", "Status is set"],
			["Starts open if", "Never"],
		]);
		await acts.run("canvas.set_container_property", { container: "more", property: "opened", value: true });
		expect(lines()[1]).toEqual(["Starts open if", "Always"]);
	});

	it("gives a tab and a column one Visible if row, Always when empty", () => {
		const { canvas, said } = mount();
		const tab = canvas.tabs.value[0];
		for (const [kind, node] of [
			["tab", tab],
			["column", tab.sections[0].columns[0]],
		] as const) {
			const rows = containerRules(kind, node);
			expect(rows.map((one) => one.label)).toEqual(["Visible if"]);
			expect(said.say(ruleValue(node, rows[0]), rows[0].empty).text).toBe("Always");
			expect(said.sentence(rows[0], "eval:doc.status=='Done'")).toBe("Visible if Status is Done");
		}
	});
});

describe("the canvas mark's lines", () => {
	it("lists each rule set on a field or container as its sentence, and none without rules", () => {
		const { canvas, said } = mount();
		const field = { ...canvas.field("subject")!, depends_on: "eval:doc.status=='Open'", read_only_depends_on: "eval:x(" };
		expect(said.lines(FIELD_RULES, field)).toEqual(["Visible if Status is Open", "Read-only if (code): x("]);
		expect(said.lines(FIELD_RULES, canvas.field("status")!)).toEqual([]);
		const more = canvas.tabs.value[0].sections[1];
		expect(said.lines(containerRules("section", more), more)).toEqual(["Visible if Status is set"]);
	});
});

function rule(key: string) {
	return FIELD_RULES.find((one) => one.key === key)!;
}
