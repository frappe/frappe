// `shell.dialog`: frappe-ui's `confirm` and `danger`, narrowed as `page.dialog` narrows them, and
// `open`, which is `page.dialog.open` on the shell's own stack, mounted by `<ShellDialogs>`.
import type { Component } from "vue";
import {
	openNarrowedDialog,
	type DialogConfirmOptions,
	type DialogDangerOptions,
	type NarrowedDialogHost,
} from "@/narrowedDialog";
import { createPageDialogs } from "./dialogs/pageDialogs";
import type { PageDialogOpenOptions } from "./dialogs/types";

/** The shell's open dialogs: nothing closes them but the reader, so there is one stack for the tab's life. */
export const shellDialogs = createPageDialogs({ source: () => "shell", isReplaying: () => false, hold: async (work) => work() });

/** `shell.dialog`: `open`, `confirm` and `danger`. Each resolves `true` when confirmed, `null` when dismissed. */
export interface ShellDialog {
	/** Renders `component` in a dialog, passing it a `close(result)` prop; the answer is what it closes with. Same contract as `page.dialog.open`. */
	open(component: Component, props?: Record<string, any>, options?: PageDialogOpenOptions): Promise<any>;
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
		open: shellDialogs.api.open,
		confirm: (options) => openNarrowedDialog("confirm", options ?? {}, host("confirm")),
		danger: (options) => openNarrowedDialog("danger", options ?? {}, host("danger")),
	};
}
