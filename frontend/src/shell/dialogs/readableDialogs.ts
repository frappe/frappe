// The tab's one list of open dialogs, for a caller that cannot see the screen. `page.dialog` and
// `shell.dialog` feed it; a self-hosted component dialog feeds it through `useReadableDialog`.
import { inject, onScopeDispose, shallowReactive, shallowRef, watch, type Ref } from "vue";
import type { DialogConfirmOptions } from "@/narrowedDialog";
import { __ } from "@/i18n";

export type ReadableDialogKind = "confirm" | "danger" | "form" | "dialog";

/** What a caller may do to a form dialog. Never set on `confirm` or `danger`: a person answers those. */
export interface DialogHandle {
	/** The fieldnames the dialog draws. */
	fieldnames: () => string[];
	values: () => Record<string, any>;
	/** Throws on a fieldname the dialog does not draw. */
	setValues: (values: Record<string, any>) => void;
	submit: () => unknown;
	close: () => void;
}

export interface ReadableDialog {
	id: number;
	kind: ReadableDialogKind;
	title: string;
	message: string;
	/** The labels of its buttons, in the order they read. */
	buttons: string[];
	handle?: DialogHandle;
}

export type ReadableDialogSpec = Omit<ReadableDialog, "id" | "handle">;

/** One dialog as `readDialogs` returns it. */
export interface ReadableDialogSnapshot extends ReadableDialogSpec {
	id: number;
	fieldnames?: string[];
	values?: Record<string, any>;
}

let nextId = 0;
const listed = shallowRef<ReadableDialog[]>([]);

/** Puts a dialog on the list; the release takes it off. */
export function listDialog(spec: ReadableDialogSpec): { dialog: ReadableDialog; release: () => void } {
	const dialog = shallowReactive<ReadableDialog>({ id: nextId++, ...spec });
	listed.value = [...listed.value, dialog];
	return { dialog, release: () => (listed.value = listed.value.filter((held) => held !== dialog)) };
}

/** The open dialogs, oldest first. */
export function readDialogs(): ReadableDialogSnapshot[] {
	return listed.value.map(({ handle, ...rest }) => ({
		...rest,
		...(handle && { fieldnames: handle.fieldnames(), values: handle.values() }),
	}));
}

/** The dialog in front that a caller may fill. */
export function frontHandle(): DialogHandle | undefined {
	return listed.value.at(-1)?.handle;
}

/** The buttons a `confirm` or `danger` draws, as frappe-ui labels them. */
export function confirmButtons(verb: "confirm" | "danger", options: DialogConfirmOptions): string[] {
	if (options.actions) return options.actions.map((action) => action.label);
	return [options.confirmLabel || (verb === "danger" ? __("Delete") : __("Confirm")), options.cancelLabel || __("Cancel")];
}

/** Lists a `confirm` or `danger` while it is open, riding the `track` that closes it. */
export function trackListed(
	verb: "confirm" | "danger",
	options: DialogConfirmOptions,
	track: (close: () => void) => () => void
) {
	return (close: () => void) => {
		const untrack = track(close);
		const { release } = listDialog({
			kind: verb,
			title: options.title ?? "",
			message: options.message ?? "",
			buttons: confirmButtons(verb, options),
		});
		return () => {
			untrack();
			release();
		};
	};
}

/** Lists the component dialog that owns `open` while it is open; `describe` is re-read as it changes. */
export function useReadableDialog(open: Ref<boolean>, describe: () => Partial<ReadableDialogSpec>) {
	let listing: ReturnType<typeof listDialog> | undefined;
	const stop = watch(
		() => (open.value ? describe() : null),
		(spec) => {
			if (!spec) {
				listing?.release();
				listing = undefined;
			} else if (listing) Object.assign(listing.dialog, spec);
			else listing = listDialog({ kind: "dialog", title: "", message: "", buttons: [], ...spec });
		},
		{ immediate: true }
	);
	onScopeDispose(() => {
		stop();
		listing?.release();
	});
}

/** Provided by a dialog host, so the component it renders can say what a caller may do to it. */
export const ListedDialogKey = Symbol("listed-dialog");

/** Gives the dialog this component renders in a host (`page.dialog.open`) a handle. */
export function useDialogHandle(handle: DialogHandle) {
	const dialog = inject<ReadableDialog | null>(ListedDialogKey, null);
	if (dialog) dialog.handle = handle;
}
