// The question a record page asks before unsaved changes are lost.
import { __ } from "@/i18n";
import type { RecordPageApi } from "@/recordPage";

export type Confirm = RecordPageApi["dialog"]["confirm"];

/** True when the reader chose to discard. */
export async function discardChanges(
	confirm: Confirm,
	message = __("This record has changes that are not saved.")
): Promise<boolean> {
	const discard = await confirm({
		title: __("Discard unsaved changes?"),
		message,
		confirmLabel: __("Discard"),
		cancelLabel: __("Keep editing"),
	});
	return !!discard;
}
