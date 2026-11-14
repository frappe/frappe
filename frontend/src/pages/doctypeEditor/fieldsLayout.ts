// `layout_from_fields` in `form_layout.py`: the Details layout the record draws from the DocType's fields.
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import type { LayoutTree } from "@/recordPage/formLayoutSource/types";

type Tab = LayoutTree[number];
type Section = Tab["sections"][number];
type Column = Section["columns"][number];

/** Breaks open containers; every other field goes in the column open last, after any `tabs` to go on from. */
export function layoutFromFields(fields: RawMetaField[], tabs: LayoutTree = []): LayoutTree {
	for (const field of fields) {
		if (field.fieldtype === "Tab Break") tabs.push({ ...container(field), sections: [] });
		else if (field.fieldtype === "Section Break") lastTab(tabs).sections.push({ ...container(field), columns: [] });
		else if (field.fieldtype === "Column Break") lastSection(tabs).columns.push({ ...container(field), fields: [] });
		else lastColumn(tabs).fields.push(field.fieldname);
	}
	deduplicateNames(tabs);
	return tabs;
}

function container(field: RawMetaField): Omit<Section, "columns"> & { name: string } {
	const keys: Record<string, unknown> = { label: field.label, dependsOn: field.depends_on };
	if (field.fieldtype === "Section Break") {
		keys.description = field.description;
		keys.collapsible = Boolean(field.collapsible);
		keys.collapsibleDependsOn = field.collapsible_depends_on;
		keys.hideBorder = Boolean(field.hide_border);
	}
	const set = Object.entries(keys).filter(([, value]) => value);
	return { name: field.fieldname, ...Object.fromEntries(set) };
}

function lastTab(tabs: LayoutTree): Tab {
	if (!tabs.length) tabs.push({ name: "first_tab", sections: [] });
	return tabs.at(-1)!;
}

function lastSection(tabs: LayoutTree): Section {
	const tab = lastTab(tabs);
	if (!tab.sections.length) tab.sections.push({ name: "section_1", columns: [] });
	return tab.sections.at(-1)!;
}

function lastColumn(tabs: LayoutTree): Column {
	const section = lastSection(tabs);
	if (!section.columns.length) section.columns.push({ name: "column_1", fields: [] });
	return section.columns.at(-1)!;
}

/** `deduplicate_names`: tabs, all sections, and each section's columns are a group each; a repeat becomes `name-2`. */
function deduplicateNames(tabs: LayoutTree) {
	const sections = tabs.flatMap((tab) => tab.sections);
	for (const group of [tabs, sections, ...sections.map((section) => section.columns)]) {
		const taken = new Set<string>();
		for (const node of group as { name?: string }[]) {
			if (taken.has(node.name!)) node.name = freeName(node.name!, taken);
			taken.add(node.name!);
		}
	}
}

function freeName(name: string, taken: Set<string>): string {
	let suffix = 2;
	while (taken.has(`${name}-${suffix}`)) suffix++;
	return `${name}-${suffix}`;
}
