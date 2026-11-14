import { describe, expect, it } from "vitest";
import { LinkFilters } from "../linkFilters";
import { RuleDraft } from "../ruleDraft";
import { RuleWords } from "../ruleWords";

const words = new RuleWords([
	{ fieldname: "status", label: "Status", fieldtype: "Select", options: "Open\nDone" },
	{ fieldname: "urgent", label: "Urgent", fieldtype: "Check" },
]);

describe("the rule dialog's draft", () => {
	it("opens a readable rule in Rules, and writes the edited tree back as the stored text", () => {
		const draft = new RuleDraft('eval:doc.status=="Open"', words);
		expect(draft.mode.value).toBe("rules");
		expect(draft.tree.value).toEqual({
			conjunction: "and",
			conditions: [{ fieldname: "status", operator: "equals", value: "Open" }],
		});
		expect(draft.changed()).toBe(false);

		draft.setTree({
			conjunction: "or",
			conditions: [
				{ fieldname: "status", operator: "equals", value: "Open" },
				{ fieldname: "urgent", operator: "equals", value: "Yes" },
			],
		});
		expect(draft.value.value).toBe('eval:doc.status === "Open" || doc.urgent');
		expect(draft.changed()).toBe(true);
		expect(new RuleDraft(draft.value.value, words).tree.value).toEqual(draft.tree.value);
	});

	it("opens an unreadable rule in Code as written, with Rules off, and changes nothing until edited", () => {
		const raw = "eval: frappe.user.has_role('System Manager')";
		const draft = new RuleDraft(raw, words);
		expect(draft.mode.value).toBe("code");
		expect(draft.code.value).toBe(" frappe.user.has_role('System Manager')");
		expect(draft.readable.value).toBe(false);
		draft.switchTo("rules");
		expect(draft.mode.value).toBe("code");
		expect(draft.changed()).toBe(false);

		draft.setCode("doc.urgent");
		expect(draft.value.value).toBe("eval:doc.urgent");
		expect(draft.readable.value).toBe(true);
		draft.switchTo("rules");
		expect(draft.tree.value.conditions).toEqual([{ fieldname: "urgent", operator: "equals", value: "Yes" }]);
	});

	it("keeps a rule that is not eval: code in the form it was written, after an edit too", () => {
		const fn = new RuleDraft("fn:toggle_vat", words);
		expect(fn.code.value).toBe("fn:toggle_vat");
		fn.setCode("fn:toggle_tax");
		expect(fn.value.value).toBe("fn:toggle_tax");

		const bare = new RuleDraft("old_field", words);
		bare.setCode("new_field");
		expect(bare.value.value).toBe("new_field");
	});

	it("clears to no rule, in Rules", () => {
		const draft = new RuleDraft("eval:weird(", words);
		draft.clear();
		expect([draft.value.value, draft.mode.value, draft.tree.value.conditions]).toEqual(["", "rules", []]);
	});

	it("does not stage link filters that name a field twice, and says why", () => {
		const filters = new LinkFilters(
			"Customer",
			[{ label: "Credit Days", value: "credit_days", fieldname: "credit_days", fieldtype: "Int" }],
			words,
		);
		const raw = JSON.stringify([["Customer", "credit_days", ">", 30]]);
		const draft = new RuleDraft(raw, filters);
		const first = { fieldname: "credit_days", operator: ">" as const, value: "30" };
		draft.setTree({
			conjunction: "and",
			conditions: [first, { fieldname: "credit_days", operator: "<" as const, value: "60" }],
		});
		expect(draft.problem.value).toContain("Credit Days has two filters");
		expect(draft.value.value).toBe(raw);
		expect(draft.changed()).toBe(false);

		draft.setTree({ conjunction: "and", conditions: [first] });
		expect(draft.problem.value).toBe("");
	});

	it("edits link filters the same way, the code as indented JSON", () => {
		const filters = new LinkFilters(
			"Customer",
			[{ label: "Disabled", value: "disabled", fieldname: "disabled", fieldtype: "Check" }],
			words,
		);
		const raw = JSON.stringify([["Customer", "disabled", "=", 0]]);
		const draft = new RuleDraft(raw, filters);
		expect(draft.tree.value.conditions).toEqual([{ fieldname: "disabled", operator: "equals", value: "No" }]);
		draft.switchTo("code");
		expect(draft.code.value).toBe('[\n  ["Customer", "disabled", "=", 0]\n]');
		expect(draft.changed()).toBe(false);
		draft.setCode('[["Customer", "disabled", "=", 1]]');
		expect(draft.value.value).toBe('[["Customer","disabled","=",1]]');
	});
});
