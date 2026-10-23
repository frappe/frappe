// The question a record page asks before unsaved changes are lost.
import { __ } from "@/i18n";
import type { RecordPageApi } from "@/recordPage";

/** True when the reader chose to discard. */
export async function discardChanges(page: RecordPageApi): Promise<boolean> {
	const discard = await page.dialog.confirm({
		title: __("Discard unsaved changes?"),
		message: __("This record has changes that are not saved."),
		confirmLabel: __("Discard"),
		cancelLabel: __("Keep editing"),
	});
	return !!discard;
}
