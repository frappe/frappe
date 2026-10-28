// `shell.dialog`: frappe-ui's `confirm` and `danger`, narrowed as `page.dialog` narrows them.
import {
	openNarrowedDialog,
	type DialogConfirmOptions,
	type DialogDangerOptions,
	type NarrowedDialogHost,
} from "@/narrowedDialog";

/** `shell.dialog`: `confirm` and `danger` only. Each resolves `true` when confirmed, `null` when dismissed. */
export interface ShellDialog {
	confirm(options: DialogConfirmOptions): Promise<true | null>;
	/** `confirm` in red, labelled Delete by default. */
	danger(options: DialogDangerOptions): Promise<true | null>;
}

/** `shell.dialog`, for the shell's life: nothing closes its dialogs but the reader. */
export function shellDialog(): ShellDialog {
	const host = (verb: string): NarrowedDialogHost => ({
		hold: async (work) => work(),
		warn: (reason) => {
			if (import.meta.env.DEV) console.warn(`[shell] shell.dialog.${verb} called ${reason}`);
		},
		failed: (exception) => console.error(`[shell] shell.dialog.${verb} onCancel threw`, exception),
		track: () => () => {},
	});
	return {
		confirm: (options) => openNarrowedDialog("confirm", options ?? {}, host("confirm")),
		danger: (options) => openNarrowedDialog("danger", options ?? {}, host("danger")),
	};
}
