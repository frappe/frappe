// The panel's list: layout sections and script items in one order, fields or a component each.
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { FormLayoutSchema } from "@framework/ui/components/FormLayout/types";
import { layoutItems, layoutSections, panelEntries, resetPanelEntryWarnings } from "../panelEntries";

const field = (fieldname: string, extra: Record<string, any> = {}) => ({
	fieldname,
	fieldtype: "Data",
	label: fieldname,
	...extra,
});

const LAYOUT: FormLayoutSchema = [
	{
		name: "main",
		label: "Details",
		sections: [
			{
				name: "organization_section",
				label: "Organization",
				columns: [{ fields: [field("organization"), field("website")] }],
			},
			{
				name: "bare",
				columns: [{ fields: [field("status")] }],
			},
			{
				name: "conditional",
				label: "Conditional",
				dependsOn: "eval:doc.with_products",
				columns: [{ fields: [field("products")] }],
			},
			{
				name: "emptied",
				label: "Emptied",
				columns: [{ fields: [field("secret", { hidden: true })] }],
			},
		],
	},
] as any;

let warnings: string[];

beforeEach(() => {
	resetPanelEntryWarnings();
	warnings = [];
	vi.spyOn(console, "warn").mockImplementation((message: string) => warnings.push(message));
});

describe("layoutSections", () => {
	it("keeps the sections the doc shows, with their visible fields flattened", () => {
		const sections = layoutSections(LAYOUT, { with_products: 0 });
		expect(sections.map((s) => s.name)).toEqual(["organization_section", "bare"]);
		expect(sections[0].fields.map((f) => f.fieldname)).toEqual(["organization", "website"]);
	});

	it("re-admits a section its condition opens", () => {
		const sections = layoutSections(LAYOUT, { with_products: 1 });
		expect(sections.map((s) => s.name)).toContain("conditional");
	});

	it("seeds the surface with names and labels only", () => {
		expect(layoutItems(layoutSections(LAYOUT, {}))).toEqual([
			{ name: "organization_section", label: "Organization" },
			{ name: "bare" },
		]);
	});
});

describe("panelEntries", () => {
	const sections = layoutSections(LAYOUT, {});

	it("renders a layout name as its fields and any other name as its component", () => {
		const Note = { render: () => null };
		const entries = panelEntries(
			[
				{ name: "identity" },
				{ name: "organization_section", label: "Organization" },
				{ name: "note", label: "Note", component: Note, props: { text: "hi" } },
			],
			sections
		);
		expect(entries.map((e) => e.fields.length)).toEqual([0, 2, 0]);
		expect(entries[2].component).toBe(Note);
		expect(entries[2].props).toEqual({ text: "hi" });
	});

	it("derives the header from the label: a built-in has none, a script can give it one", () => {
		const entries = panelEntries(
			[{ name: "shares" }, { name: "shares_named", label: "Shared with" }],
			sections
		);
		expect(entries[0].label).toBeUndefined();
		expect(entries[1].label).toBe("Shared with");
	});

	it("reads `opened` beside a label, and warns once where there is no header for it", () => {
		const entries = panelEntries(
			[
				{ name: "a", label: "A", opened: false },
				{ name: "b", label: "B" },
				{ name: "identity", opened: false },
			],
			sections
		);
		expect(entries.map((e) => e.opened)).toEqual([false, true, true]);
		panelEntries([{ name: "identity", opened: false }], sections);
		expect(warnings).toEqual([
			"[record-page] panel section 'identity' sets opened but has no label, so no header to open or shut; opened is ignored.",
		]);
	});
});
