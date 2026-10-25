// Lands the reader on a form field: its tab first, then its cell, polled for while the tab's panel mounts.
import { nextTick } from "vue";
import { identifyTabs } from "@framework/ui/components/FormLayout/tabIdentity";
import type { FormLayoutSchema } from "@framework/ui/components/FormLayout/types";
import type { FieldErrors } from "@/recordPage";

export interface FieldLanding {
	root: () => HTMLElement | null | undefined;
	layout: () => FormLayoutSchema;
	showTab: (identity: string) => void;
}

/** True once the cell is in view, with the cursor in its control when `cursor` is set. */
export async function landOnField(form: FieldLanding, fieldname: string, cursor: boolean) {
	const tab = tabOf(form.layout(), fieldname);
	if (tab) form.showTab(tab.identity);
	// The strip mounts a tab's panel a frame after the model moves.
	for (let frame = 0; frame < 10; frame++) {
		await nextTick();
		const cell = form
			.root()
			?.querySelector<HTMLElement>(`.field[data-fieldname="${fieldname}"]`);
		// A form locked while its save runs takes no cursor until the lock lifts.
		if (cell && !cell.closest("[inert]")) {
			cell.scrollIntoView({ block: "center" });
			if (cursor) cell.querySelector<HTMLElement>("input, textarea, select, button")?.focus();
			return true;
		}
		await new Promise(requestAnimationFrame);
	}
	return false;
}

/** Lands on the first field the marks name, in form order, with the cursor in it. */
export function landOnFirstMarked(errors: FieldErrors, form: FieldLanding, doc: Record<string, any>) {
	const fieldname = errors.firstMarked(form.layout(), doc);
	if (fieldname) void landOnField(form, fieldname, true);
}

/** The form tab that holds the field. */
export function tabOf(layout: FormLayoutSchema, fieldname: string) {
	return identifyTabs(layout).find((one) =>
		one.sections.some((section) =>
			section.columns.some((column) =>
				column.fields.some((field) => field.fieldname === fieldname)
			)
		)
	);
}
