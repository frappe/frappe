// The child editor's Grid columns group: which fields the grid shows (`in_list_view`), how wide
// (`columns` 1 to 10, or Auto), in the child's field order, against the record page's form width.
import { computed } from "vue";
import { DROPPED_FIELDTYPES, gridColumnWidth } from "@framework/ui/FormLayout";
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import { acts } from "@/acts/dispatcher";
import type { DesignCanvas } from "./designCanvas";

/** The record page's Details column. */
export const FORM_PX = 728;
/** The grid's own tracks: the checkbox, the row number and the row menu. */
export const GRID_FIXED_PX = 120;
export const MAX_COLUMNS = 10;
const NOT_A_COLUMN = new Set(
	[...DROPPED_FIELDTYPES].filter((type) => type !== "Button" && type !== "HTML").concat(["Table", "Table MultiSelect"]),
);

export class GridColumns {
	readonly columns = computed(() => this.canvas.working.value.fields.filter((field) => field.in_list_view && isColumn(field)));
	/** The child's other fields that a grid column can show. */
	readonly candidates = computed(() =>
		this.canvas.working.value.fields.filter((field) => !field.in_list_view && isColumn(field)),
	);
	readonly fit = computed(() => {
		const room = FORM_PX - GRID_FIXED_PX;
		const used = this.columns.value.reduce((sum, field) => sum + columnWidth(field), 0);
		return { room, used, over: used > room };
	});

	constructor(private canvas: DesignCanvas) {}

	/** One step narrower or wider; below 1 is Auto, the type's own width. */
	step(field: RawMetaField, by: -1 | 1) {
		const next = Math.max(0, Math.min(MAX_COLUMNS, (Number(field.columns) || 0) + by));
		this.set(field.fieldname, "columns", next);
	}

	add(fieldname: string) {
		this.set(fieldname, "in_list_view", 1);
	}

	remove(fieldname: string) {
		this.set(fieldname, "in_list_view", 0);
	}

	/** A column moves by moving its field to just before the column it lands on, or after the last. */
	move(fieldname: string, toColumn: number) {
		const fields = this.canvas.working.value.fields.filter((field) => field.fieldname !== fieldname);
		const others = this.columns.value.filter((field) => field.fieldname !== fieldname);
		const anchor = others[toColumn];
		const index = anchor ? fields.indexOf(anchor) : fields.indexOf(others.at(-1)!) + 1;
		void acts.perform("fields.reorder_field", { fieldname, index });
	}

	private set(fieldname: string, property: string, value: number) {
		void acts.perform("fields.set_field_property", { fieldname, property, value });
	}
}

/** A grid column's width in px: its `columns`, else its type's own. */
export function columnWidth(field: RawMetaField): number {
	return gridColumnWidth({ fieldtype: field.fieldtype, gridColumns: Number(field.columns) || undefined });
}

function isColumn(field: RawMetaField): boolean {
	return !field.hidden && !NOT_A_COLUMN.has(field.fieldtype);
}
