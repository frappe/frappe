import type {
	Column,
	Section,
} from "../../components/FormLayout/types";

/**
 * The section presentation both stored-layout paths carry, in one vocabulary.
 * `LayoutTreeSection` (a Form Layout row) and `PageDialogSection` (a script's
 * dialog) each name these keys slightly differently; each maps onto this before
 * building, so neither can quietly grow a different default.
 */
export interface SectionSpec {
	name?: string;
	label?: string;
	hideLabel?: boolean;
	hideBorder?: boolean;
	collapsible?: boolean;
	/** Explicit initial state; open when unset (see `buildSection`). */
	opened?: boolean;
	dependsOn?: string;
}

/**
 * The one `Section` constructor for the experimental layout sources.
 *
 * Sections open by default, collapsible or not — only an explicit
 * `opened: false` closes one. `buildLayoutFromMeta`'s `newSection` agrees by
 * construction (it has no `opened` source of its own and defaults to open), so
 * a collapsible section no longer opens or closes depending on which of the
 * three paths built it.
 */
export function buildSection(spec: SectionSpec, columns: Column[]): Section {
	return {
		name: spec.name,
		label: spec.label,
		hideLabel: Boolean(spec.hideLabel),
		hideBorder: Boolean(spec.hideBorder),
		collapsible: Boolean(spec.collapsible),
		opened: spec.opened !== false,
		dependsOn: spec.dependsOn,
		columns,
	};
}

/** The matching `Column` constructor; `hideLabel` is carried, not dropped. */
export function buildColumn(
	spec: { name?: string; label?: string; hideLabel?: boolean },
	fields: Column["fields"]
): Column {
	return {
		name: spec.name,
		label: spec.label,
		hideLabel: Boolean(spec.hideLabel),
		fields,
	};
}
