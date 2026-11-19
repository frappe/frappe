import { acts } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import type { DesignCanvas } from "./designCanvas";
import { newFieldname } from "./editorModel";
import { typeOf } from "./fieldtypes";

/** Where a new field goes: a section's column and index, or just a tab (its first section's end). */
export type FieldPlace = { section: string; column: string; index?: number } | { tab?: string };

/** A listed type as a drag carries it; a dragged field is its fieldname string. */
export type NewType = { type: string };

/** A field of a listed type, labelled by the type, put at `place`; its label takes the caret. */
export async function addFieldType(canvas: DesignCanvas, name: string, place: FieldPlace) {
	const before = canvas.working.value.fields.length;
	await acts.perform("fields.add_field", { label: freeLabel(canvas, __(name)), ...typeOf(name), ...place });
	if (canvas.working.value.fields.length > before) focusLabel();
}

/** "Data", else "Data 2" and on: a label whose fieldname no field has. */
function freeLabel(canvas: DesignCanvas, base: string) {
	for (let count = 1; ; count++) {
		const label = count === 1 ? base : `${base} ${count}`;
		if (!canvas.field(newFieldname(canvas.working.value, label))) return label;
	}
}

function focusLabel() {
	requestAnimationFrame(() => {
		const input = document.querySelector<HTMLInputElement>("[data-editor-panel] [data-panel-label]");
		input?.focus();
		input?.select();
	});
}
