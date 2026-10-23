// The question a record page asks before unsaved changes are lost.
import type { RecordPageApi } from "@/recordPage";

/** True when the reader chose to discard. */
export async function discardChanges(page: RecordPageApi): Promise<boolean> {
	const discard = await page.dialog.confirm({
		title: "Discard unsaved changes?",
		message: "This record has changes that are not saved.",
		confirmLabel: "Discard",
		cancelLabel: "Keep editing",
	});
	return !!discard;
}
