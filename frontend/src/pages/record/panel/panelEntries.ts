// What the panel draws, item by item: the surface's visible list joined against the Side
// Panel layout. A name the layout carries renders fields; any other renders its component.
import type { Component } from "vue";
import { resolveLayout } from "@framework/ui/FormLayout";
import type { FieldNode, FormLayoutSchema, Section } from "@framework/ui/FormLayout/types";
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
	/** Drawn at the right of the header; present only beside a label. */
	actions?: Component;
	/** An item drawn inside this one's component instead of as a section of its own. */
	embedded?: PanelEntry;
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
		if (label && opened !== undefined) item.opened = opened;
		return item;
	});
}

/**
 * The surface's visible items, each resolved to what it renders. `opened` and `actions`
 * are read only beside a label: a section with no header has no place for them, so each is
 * a dev warning.
 */
export function panelEntries(items: PanelSectionItem[], sections: LayoutSection[]): PanelEntry[] {
	const byName = new Map(sections.map((section) => [section.name, section]));
	return items.map((item) => {
		if (!item.label) warnHeaderKeys(item);
		const section = byName.get(item.name);
		return {
			name: item.name,
			label: item.label || undefined,
			opened: item.label ? item.opened !== false : true,
			fields: section?.fields ?? [],
			component: section ? undefined : item.component,
			props: section ? undefined : item.props,
			actions: item.label ? item.actions : undefined,
		};
	});
}

/**
 * The quick actions right after the identity draw inside it, between its title and its
 * tags: one block to the eye. Moved anywhere else, or given a header, they are a section
 * like any other.
 */
export function embedQuickActions(entries: PanelEntry[]): PanelEntry[] {
	return entries.flatMap((entry, index) => {
		if (embeds(entry, entries[index + 1])) return [{ ...entry, embedded: entries[index + 1] }];
		if (embeds(entries[index - 1], entry)) return [];
		return [entry];
	});
}

function embeds(host?: PanelEntry, next?: PanelEntry) {
	return host?.name === "identity" && next?.name === "quick_actions" && !next.label;
}

// The panel is one column, so a section's columns flatten into one list.
function visibleFields(section: Section) {
	return section.columns.flatMap((column) => column.fields).filter((field) => !field.hidden);
}

const warned = new Set<string>();

const HEADER_KEYS = ["opened", "actions"] as const;

function warnHeaderKeys(item: PanelSectionItem) {
	for (const key of HEADER_KEYS) {
		if (item[key] !== undefined) warnWithoutHeader(item.name, key);
	}
}

function warnWithoutHeader(name: string, key: string) {
	const id = `${name}:${key}`;
	if (!import.meta.env.DEV || warned.has(id)) return;
	warned.add(id);
	console.warn(
		`[record-page] panel section '${name}' sets ${key} but has no label, so no header to draw it in; ${key} is ignored.`
	);
}

/** Test seam: the warn-once memory is module state. */
export function resetPanelEntryWarnings(): void {
	warned.clear();
}
