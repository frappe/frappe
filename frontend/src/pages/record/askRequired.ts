import { defineAsyncComponent } from "vue";
import type { RouteLocationRaw } from "vue-router";
import type { FormLayoutSchema } from "@framework/ui/FormLayout/types";
import { __ } from "@/i18n";
import type { RecordPageApi } from "@/recordPage";
import { cancelledError } from "./saveResponse";

// Loaded when a save first needs it, so the page JS stays small.
const RequiredFieldsDialog = defineAsyncComponent(() => import("./dialogs/RequiredFieldsDialog.vue"));

/** Resolves the values of the asked fields; Esc, the X and Cancel stop the save, leaving the draft dirty. */
export async function askRequired(
	dialog: RecordPageApi["dialog"],
	layout: FormLayoutSchema,
	doc: Record<string, any>,
	doctype: string,
	submitting = false,
	editRoute?: RouteLocationRaw | null
): Promise<Record<string, any>> {
	const props = { layout, doc, doctype, submitting, editRoute };
	const values = await dialog.open(RequiredFieldsDialog, props, { title: __("Required fields") });
	if (!values) throw cancelledError();
	return values;
}
