// What the panel draws, item by item: the surface's visible list joined against the Side
// Panel layout. A name the layout carries renders fields; any other renders its component.
import type { Component } from "vue";
import { resolveLayout } from "@framework/ui/components/FormLayout/resolveLayout";
import type { FieldNode, FormLayoutSchema, Section } from "@framework/ui/components/FormLayout/types";
import { sectionName } from "@/recordPage/formLayoutSource/sectionName";
import type { PanelSectionItem } from "@/recordPage";

export interface PanelEntry {
	name: string;
	/** Present only on a section with a header, which is what the chevron toggles. */
	label?: string;
	/** Where the header starts, when it has one; read by the reader's memory as the default. */
	opened: boolean;
	fields: FieldNode[];
	component?: Component;
	props?: Record<string, any>;
}

/** One section of the layout as the surface addresses it: named, and labelled only when it shows a label. */
export interface LayoutSection {
	name: string;
	label?: string;
	opened?: boolean;
	fields: FieldNode[];
}

/**
 * The layout's sections as they resolve against the doc: `dependsOn` folded in, hidden
 * fields dropped, and a section left with no field dropped with them.
 */
export function layoutSections(layout: FormLayoutSchema, doc: Record<string, any>): LayoutSection[] {
	return resolveLayout(layout, doc)
		.filter((tab) => !tab.hidden)
		.flatMap((tab) => tab.sections)
		.filter((section) => !section.hidden)
		.map((section) => ({ section, fields: visibleFields(section) }))
		.filter((entry) => entry.fields.length)
		.map(({ section, fields }) => ({
			name: sectionName(section),
			label: section.hideLabel ? undefined : section.label || undefined,
			opened: section.opened,
			fields,
		}));
}

/** What the host seeds the surface with for the layout's part: names and labels, no fields. */
export function layoutItems(sections: LayoutSection[]): PanelSectionItem[] {
	return sections.map(({ name, label, opened }) => {
		const item: PanelSectionItem = { name };
		if (label) item.label = label;
		if (opened !== undefined) item.opened = opened;
		return item;
	});
}

/**
 * The surface's visible items, each resolved to what it renders. `opened` is read only
 * beside a label: a section with no header has nothing to open, so it is a dev warning.
 */
export function panelEntries(items: PanelSectionItem[], sections: LayoutSection[]): PanelEntry[] {
	const byName = new Map(sections.map((section) => [section.name, section]));
	return items.map((item) => {
		if (item.opened !== undefined && !item.label) warnOpenedWithoutHeader(item.name);
		const section = byName.get(item.name);
		return {
			name: item.name,
			label: item.label || undefined,
			opened: item.label ? item.opened !== false : true,
			fields: section?.fields ?? [],
			component: section ? undefined : item.component,
			props: section ? undefined : item.props,
		};
	});
}

// The panel is one column, so a section's columns flatten into one list.
function visibleFields(section: Section) {
	return section.columns.flatMap((column) => column.fields).filter((field) => !field.hidden);
}

const warned = new Set<string>();

function warnOpenedWithoutHeader(name: string) {
	if (!import.meta.env.DEV || warned.has(name)) return;
	warned.add(name);
	console.warn(
		`[record-page] panel section '${name}' sets opened but has no label, so no header to open or shut; opened is ignored.`
	);
}

/** Test seam: the warn-once memory is module state. */
export function resetPanelEntryWarnings(): void {
	warned.clear();
}
