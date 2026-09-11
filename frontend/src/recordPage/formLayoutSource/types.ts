// The `Form Layout` doctype's wire shapes: `get_form_layouts` returns rows as
// authored — fieldnames stay strings; the meta join happens client-side.

export type FormLayoutType = "Details" | "Side Panel" | "Quick Entry";

export interface LayoutTreeColumn {
	name?: string;
	label?: string;
	hideLabel?: boolean;
	fields: string[];
}

export interface LayoutTreeSection {
	name?: string;
	label?: string;
	hideLabel?: boolean;
	hideBorder?: boolean;
	collapsible?: boolean;
	opened?: boolean;
	dependsOn?: string;
	columns: LayoutTreeColumn[];
}

export interface LayoutTreeTab {
	name?: string;
	label?: string;
	dependsOn?: string;
	sections: LayoutTreeSection[];
}

export type LayoutTree = LayoutTreeTab[];

export interface FormLayoutRow {
	name: string | number;
	condition?: string | null;
	layout: LayoutTree;
}

export interface FormLayoutsResponse {
	/** Every row for the `(dt, type)`, `creation asc`, layouts parsed. */
	layouts: FormLayoutRow[];
	/** The meta-derived layout, rendered when no row applies. */
	fallback: LayoutTree;
}
