// What a Customize save wrote, as its toast says it: new custom fields, property changes, the layout.
import { __, __n } from "@/i18n";
import { customFieldname } from "./customizeRules";
import type { FlatEdit } from "./editorModel";

/** A new field's own properties count with the field; a property set twice counts once. */
export function saveSummary(edits: readonly FlatEdit[]): string {
	const added = new Set<string>();
	const changed = new Set<string>();
	let layout = false;
	for (const edit of edits) {
		const fieldname = edit.fieldname as string;
		if (edit.act === "fields.add_field") added.add(fieldname || customFieldname(edit.label as string));
		else if (edit.act === "fields.rename_field" && added.delete(fieldname)) added.add(edit.new_fieldname as string);
		else if (edit.act.startsWith("canvas.") || edit.act.startsWith("layouts.")) layout = true;
		else if (!added.has(fieldname)) for (const property of properties(edit)) changed.add(`${fieldname}.${property}`);
	}
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

function properties(edit: FlatEdit): string[] {
	if (edit.act === "fields.reset_field_property") return [edit.property as string];
	if (edit.act !== "fields.set_field_property") return [];
	return edit.properties ? Object.keys(edit.properties as object) : [edit.property as string];
}
