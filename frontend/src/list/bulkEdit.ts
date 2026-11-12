// The bulk Edit: which fields it can set, and the one request that sets them on the selection.
import {
	bulkUpdateDocuments,
	isBulkQueued,
	type BulkSelection,
	type BulkUpdate,
} from "@framework/ui/api";
import type { RawMetaField } from "@framework/ui/FormLayout";
import { NO_VALUE } from "@framework/ui/FormLayout";
import type { ListRows } from "./useListRows";

export interface EditOutcome {
	updated: string[];
	failed: { name: string; error: string }[];
	/** The run went to the background; its result is not known yet. */
	queued?: { task_id: string };
}

/** A field the Edit can set; a child field sets every row of its table. */
export interface EditableField {
	key: string;
	label: string;
	field: RawMetaField;
	/** The table field of the record, for a child field. */
	table?: string;
	doctype: string;
}

const NEVER_SET = ["Read Only", "Button", "Image", "Attach Image", "Table", "Table MultiSelect"];

/** v1's rule: a value field that is neither read-only, hidden nor virtual. */
export function isEditable(field: RawMetaField): boolean {
	return Boolean(
		field.fieldname &&
			!NO_VALUE.has(field.fieldtype) &&
			!NEVER_SET.includes(field.fieldtype) &&
			!field.hidden &&
			!field.read_only &&
			!(field as { is_virtual?: number }).is_virtual
	);
}

export function editableFields(
	doctype: string,
	fields: RawMetaField[],
	children: Record<string, RawMetaField[]>
): EditableField[] {
	const own = fields.filter(isEditable).map((field) => ({
		key: field.fieldname,
		label: field.label || field.fieldname,
		field,
		doctype,
	}));
	const nested = fields
		.filter((table) => table.fieldtype === "Table" && table.options)
		.flatMap((table) =>
			(children[table.options!] ?? []).filter(isEditable).map((field) => ({
				key: `${table.fieldname}.${field.fieldname}`,
				label: `${field.label || field.fieldname} (${table.label || table.fieldname})`,
				field,
				table: table.fieldname,
				doctype: table.options!,
			}))
		);
	return [...own, ...nested].sort((a, b) => a.label.localeCompare(b.label));
}

/** One `values` and one `child_values` for every record; an empty value clears the field, as v1's does. */
export function updateFrom(picked: { field: EditableField; value: unknown }[]): BulkUpdate {
	const update: BulkUpdate = {};
	for (const { field, value } of picked) {
		const set = value === "" || value === undefined ? null : value;
		if (field.table) {
			update.child_values = {
				...update.child_values,
				[field.table]: { ...update.child_values?.[field.table], [field.field.fieldname]: set },
			};
		} else {
			update.values = { ...update.values, [field.field.fieldname]: set };
		}
	}
	return update;
}

export async function updateRows(
	doctype: string,
	rows: Pick<ListRows, "reload">,
	selection: BulkSelection,
	update: BulkUpdate
): Promise<EditOutcome> {
	const { data } = await bulkUpdateDocuments(doctype, selection, update);
	rows.reload();
	if (isBulkQueued(data)) return { updated: [], failed: [], queued: { task_id: data.task_id } };
	return { updated: data.done, failed: data.failed };
}
