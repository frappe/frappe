// What a Customize save wrote, as its toast says it: new custom fields, property changes, the layout.
import { __, __n } from "@/i18n";
import { customFieldname } from "./customizeRules";
import { editedProperties } from "./customizeView";
import type { SaveError } from "./designCanvas";
import type { FlatEdit } from "./editorModel";

export interface SummaryFilter {
	/** The server's refusals: the save restored those values. */
	skipped?: readonly SaveError[];
	/** A property staged back to its loaded value writes nothing. */
	unchanged?: (fieldname: string, property: string) => boolean;
}

/** A new field's own properties count with the field; a property set twice counts once. */
export function saveSummary(edits: readonly FlatEdit[], filter: SummaryFilter = {}): string {
	const added = new Set<string>();
	const changed = new Set<string>();
	let layout = false;
	for (const edit of edits) {
		const fieldname = edit.fieldname as string;
		if (edit.act === "fields.add_field") added.add(fieldname || customFieldname(edit.label as string));
		else if (edit.act === "fields.fetch_field") added.add(fieldname);
		else if (edit.act === "fields.add_child_table") added.add(edit.table_field as string);
		else if (edit.act === "fields.rename_field" && added.delete(fieldname)) added.add(edit.new_fieldname as string);
		else if (edit.act === "fields.delete_field" && added.delete(fieldname)) continue;
		else if (edit.act.startsWith("canvas.") || edit.act.startsWith("layouts.")) layout = true;
		else if (!added.has(fieldname))
			for (const property of editedProperties(edit))
				if (!filter.unchanged?.(fieldname, property)) changed.add(`${fieldname}.${property}`);
	}
	for (const { target } of filter.skipped ?? []) changed.delete(`${target.fieldname}.${target.property}`);
	const fields = added.size;
	const parts = [
		fields && __n("{0} custom field", "{0} custom fields", fields, [fields]),
		changed.size && __n("{0} property change", "{0} property changes", changed.size, [changed.size]),
		layout && __("the layout"),
	].filter(Boolean) as string[];
	if (!parts.length) return __("Saved");
	const last = parts.pop()!;
	return parts.length
		? __("Saved {0} and {1}.", [parts.join(", "), last])
		: __("Saved {0}.", [last]);
}

