// The `Form Layout` doctype's wire shapes: `get_form_layouts` returns rows as
// authored — fieldnames stay strings, inline fields stay dicts; the meta join happens client-side.
import type { RawMetaField } from "@framework/ui/FormLayout/types";

export type FormLayoutType = "Details" | "Side Panel" | "Quick Entry" | "New Record";

export interface LayoutTreeColumn {
	name?: string;
	label?: string;
	hideLabel?: boolean;
	fields: (string | InlineField)[];
}

/** A field a Quick Entry or New Record row defines itself; it replaces a read-only meta field of its name. */
export type InlineField = RawMetaField;

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
	/** `null` for the app's layout file, which comes last and only when no row is the default. */
	name: string | number | null;
	condition?: string | null;
	layout: LayoutTree;
	/** Fieldnames the row keeps off its layout on purpose; Details and New Record read it. */
	omitted?: string[];
}

export interface FormLayoutsResponse {
	/** Every row for the `(dt, type)`, `creation asc`, layouts parsed; `New Record` with none gets the `Details` rows. */
	layouts: FormLayoutRow[];
	/** Rendered when no row applies: the meta layout, or the mandatory-only set for `Quick Entry`. */
	fallback: LayoutTree;
	/** `Quick Entry` only: whether Create opens a dialog rather than the full-page new record. */
	dialog?: boolean;
	/** Each `Table` field's child doctype → its Details rows, which its row dialog reads; `[]` when it has none. */
	children?: Record<string, FormLayoutRow[]>;
}
