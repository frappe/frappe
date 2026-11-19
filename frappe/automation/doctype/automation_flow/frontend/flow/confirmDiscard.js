import { dialog } from "frappe-ui";
import { __ } from "frappe/i18n";

/** Asks before unsaved changes are lost; true when the person chose to discard them. */
export function confirmDiscard(message = __("This flow has changes that are not saved.")) {
	return new Promise((resolve) => {
		dialog.confirm({
			title: __("Discard unsaved changes?"),
			message,
			confirmLabel: __("Discard"),
			cancelLabel: __("Keep editing"),
			onConfirm: ({ close }) => {
				close();
				resolve(true);
			},
			onCancel: () => resolve(false),
		});
	});
}
