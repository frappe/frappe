// The `Form Layout` doctype's wire shapes: `get_form_layouts` returns rows as
// authored — fieldnames stay strings; the meta join happens client-side.

export type FormLayoutType = "Details" | "Side Panel" | "Quick Entry" | "New Record";

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
	/** Every row for the `(dt, type)`, `creation asc`, layouts parsed; `New Record` with none gets the `Details` rows. */
	layouts: FormLayoutRow[];
	/** Rendered when no row applies: the meta layout, or the mandatory-only set for `Quick Entry`. */
	fallback: LayoutTree;
	/** `Quick Entry` only: whether Create opens a dialog rather than the full-page new record. */
	dialog?: boolean;
}
