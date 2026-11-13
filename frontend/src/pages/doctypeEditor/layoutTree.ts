// The canvas acts on one layout tree, as `frappe/desk/doctype_editor/layout_tree.py` applies them
// on save. Keep the two in step: the canvas draws this result before the server sees the edits.
import type { LayoutTree } from "@/recordPage/formLayoutSource/types";

export type LayoutTreeTab = LayoutTree[number];
export type LayoutTreeSection = LayoutTreeTab["sections"][number];
export type LayoutTreeColumn = LayoutTreeSection["columns"][number];

type Named = { name?: string; label?: string };

export const CONTAINER_PROPERTIES = [
	"label",
	"hideLabel",
	"description",
	"hideBorder",
	"collapsible",
	"opened",
	"dependsOn",
	"collapsibleDependsOn",
];

/** An edit the server would refuse too; the message is the server's, and `template` translates it. */
export class EditRefused extends Error {
	constructor(
		readonly template: string,
		readonly args: string[] = [],
	) {
		super(template.replace(/\{(\d+)\}/g, (_, at) => args[Number(at)]));
	}
}

/** Edits `tabs` in place; the caller hands it a copy. */
export class LayoutTreeEditor {
	constructor(readonly tabs: LayoutTree) {}

	sections(): LayoutTreeSection[] {
		return this.tabs.flatMap((tab) => tab.sections);
	}

	columns(): LayoutTreeColumn[] {
		return this.sections().flatMap((section) => section.columns);
	}

	fieldnames(): string[] {
		return this.columns().flatMap((column) =>
			column.fields.filter((entry): entry is string => typeof entry === "string"),
		);
	}

	add_tab({ name, label, index }: { name?: string; label?: string; index?: number }) {
		insert(this.tabs, { ...newNode(name, label), sections: [] }, index);
		assignNames(this.tabs, "tab");
	}

	add_section({ tab, name, label, index }: { tab: string; name?: string; label?: string; index?: number }) {
		const section = { ...newNode(name, label), columns: [{ name: "column_1", fields: [] }] };
		insert(this.tab(tab).sections, section, index);
		assignNames(this.sections(), "section");
	}

	add_column({ section, name, index }: { section: string; name?: string; index?: number }) {
		const columns = this.section(section).columns;
		insert(columns, { ...newNode(name), fields: [] }, index);
		assignNames(columns, "column");
	}

	remove_tab({ tab }: { tab: string }) {
		const node = this.tab(tab);
		if (this.tabs.length === 1) throw new EditRefused("A layout keeps at least one tab.");
		const at = this.tabs.indexOf(node);
		const receiver = at ? this.tabs[at - 1] : this.tabs[1];
		receiver.sections.push(...node.sections);
		remove(this.tabs, node);
	}

	remove_section({ section }: { section: string }) {
		const [tab, node] = this.parentOfSection(section);
		const at = tab.sections.indexOf(node);
		remove(tab.sections, node);
		const receiver = tab.sections[Math.max(at - 1, 0)];
		const fields = node.columns.flatMap((column) => column.fields);
		if (fields.length && receiver?.columns.length) receiver.columns.at(-1)!.fields.push(...fields);
	}

	remove_column({ column, section }: { column: string; section?: string }) {
		const [parent, node] = this.parentOfColumn(column, section);
		const at = parent.columns.indexOf(node);
		remove(parent.columns, node);
		parent.columns[Math.max(at - 1, 0)]?.fields.push(...node.fields);
	}

	move_tab({ tab, index }: { tab: string; index: number }) {
		const node = this.tab(tab);
		remove(this.tabs, node);
		this.tabs.splice(index, 0, node);
	}

	move_section({ section, tab, index }: { section: string; tab: string; index: number }) {
		const [from, node] = this.parentOfSection(section);
		remove(from.sections, node);
		this.tab(tab).sections.splice(index, 0, node);
	}

	move_column(edit: { column: string; section?: string; to_section: string; index?: number }) {
		const [from, node] = this.parentOfColumn(edit.column, edit.section);
		remove(from.columns, node);
		const columns = this.section(edit.to_section).columns;
		// Column names repeat across sections: one that clashes in its new section takes a new name.
		if (columns.some((other) => other.name === node.name)) delete node.name;
		insert(columns, node, edit.index);
		assignNames(columns, "column");
	}

	set_container_property(edit: { container: string; section?: string; property: string; value: unknown }) {
		const { container, section, property, value } = edit;
		if (!CONTAINER_PROPERTIES.includes(property)) {
			throw new EditRefused("{0} is not a container property.", [property]);
		}
		const found = section ? this.column(container, section) : this.container(container);
		const node = found as unknown as Record<string, unknown>;
		if (value == null || value === "" || value === false || value === 0) delete node[property];
		else node[property] = value;
	}

	place_field(edit: { fieldname: string; column?: string; section?: string; tab?: string; index?: number }) {
		this.unplace_field(edit);
		let fields: LayoutTreeColumn["fields"];
		if (edit.tab) {
			const target = this.tab(edit.tab);
			if (!target.sections.length) this.add_section({ tab: edit.tab });
			fields = target.sections[0].columns.at(-1)!.fields;
		} else {
			fields = this.column(edit.column!, edit.section).fields;
		}
		insert(fields, edit.fieldname, edit.index);
	}

	unplace_field({ fieldname }: { fieldname: string }) {
		for (const column of this.columns()) {
			column.fields = column.fields.filter((entry) => entry !== fieldname);
		}
	}

	rename_field(old: string, renamed: string) {
		for (const column of this.columns()) {
			column.fields = column.fields.map((entry) => (entry === old ? renamed : entry));
		}
	}

	tab(name: string): LayoutTreeTab {
		return find(this.tabs, name);
	}

	section(name: string): LayoutTreeSection {
		return find(this.sections(), name);
	}

	/** Column names repeat across sections, so an unscoped name must be unique in the layout. */
	column(name: string, section?: string): LayoutTreeColumn {
		if (section) return find(this.section(section).columns, name);
		const matches = this.columns().filter((column) => column.name === name);
		if (matches.length > 1) throw new EditRefused("Name the section of column {0}.", [name]);
		return find(matches, name);
	}

	container(name: string): LayoutTreeTab | LayoutTreeSection {
		return find<LayoutTreeTab | LayoutTreeSection>([...this.tabs, ...this.sections()], name);
	}

	private parentOfSection(name: string): [LayoutTreeTab, LayoutTreeSection] {
		const node = this.section(name);
		return [this.tabs.find((tab) => tab.sections.includes(node))!, node];
	}

	private parentOfColumn(name: string, section?: string): [LayoutTreeSection, LayoutTreeColumn] {
		const node = this.column(name, section);
		return [this.sections().find((each) => each.columns.includes(node))!, node];
	}
}

/** `assign_names` in `form_layout.py`: a new node takes its label's slug, else `<kind>_<position>`. */
export function assignNames(nodes: Named[], kind: string) {
	const taken = new Set(nodes.map((node) => node.name).filter(Boolean));
	nodes.forEach((node, at) => {
		if (node.name) return;
		let name = slugify(node.label) || `${kind}_${at + 1}`;
		if (taken.has(name)) name = `${name}_${at + 1}`;
		node.name = name;
		taken.add(name);
	});
}

function slugify(label?: string): string {
	return (label ?? "")
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, "_")
		.replace(/^_+|_+$/g, "");
}

function newNode(name?: string, label?: string): Named {
	return { ...(name ? { name } : {}), ...(label ? { label } : {}) };
}

function find<T extends Named>(nodes: T[], name: string): T {
	const node = nodes.find((each) => each.name === name);
	if (!node) throw new EditRefused("This layout has no {0}.", [name]);
	return node;
}

function insert<T>(siblings: T[], node: T, index?: number) {
	siblings.splice(index ?? siblings.length, 0, node);
}

function remove<T>(siblings: T[], node: T) {
	siblings.splice(siblings.indexOf(node), 1);
}
