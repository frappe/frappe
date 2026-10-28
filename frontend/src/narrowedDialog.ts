// `confirm` and `danger`: frappe-ui's own dialogs, narrowed to the options named here.
// `shell.dialog` and `page.dialog` both open them through `openNarrowedDialog`.
import { dialog as frappeDialog } from "frappe-ui";

/** What a `confirm`/`danger` callback receives: the desk's own object, not frappe-ui's. */
export interface DialogControl {
	/** Closes the dialog; the verb's promise settles from the verb, as ever. */
	close(): void;
	/** Shows an inline error and re-enables the buttons; `null` clears it. */
	setError(message: string | null): void;
}

/** One button on a `confirm`/`danger`: the five props the desk forwards. */
export interface DialogConfirmAction {
	label: string;
	variant?: string;
	theme?: string;
	icon?: string;
	/** Omitted means the button only dismisses, and the verb resolves `null`. */
	onClick?: (control: DialogControl) => any;
}

/** `confirm`'s options; a key not named here is dropped, not forwarded. */
export interface DialogConfirmOptions {
	title?: string;
	message?: string;
	confirmLabel?: string;
	cancelLabel?: string;
	theme?: string;
	icon?: string;
	size?: string;
	dismissible?: boolean;
	onConfirm?: (control: DialogControl) => any;
	onCancel?: () => any;
	/** Custom buttons; when given, the confirm/cancel pair is not rendered. */
	actions?: DialogConfirmAction[];
}

/** `danger` forces red and its own icon, so it names neither. */
export type DialogDangerOptions = Omit<DialogConfirmOptions, "theme" | "icon">;

export interface NarrowedDialogHost {
	/** Runs one of the author's callbacks. */
	hold: <T>(work: () => Promise<T> | T) => Promise<T>;
	/** Says what the call passed that is not forwarded. */
	warn: (reason: string) => void;
	/** Reports an `onCancel` that threw. */
	failed: (exception: unknown) => void;
	/** Keeps a way to close the open dialog; returns the release. */
	track: (close: () => void) => () => void;
}

// frappe-ui's `ConfirmArgs`, named key by key: an option not named here is dropped.
const CONFIRM_OPTIONS = [
	"title",
	"message",
	"confirmLabel",
	"cancelLabel",
	"theme",
	"icon",
	"size",
	"dismissible",
	"onConfirm",
	"onCancel",
	"actions",
];

// frappe-ui forces red and its own icon on `danger`, so passing either is the mistake warned about.
const DANGER_OPTIONS = CONFIRM_OPTIONS.filter((option) => option !== "theme" && option !== "icon");

// frappe-ui's `DialogAction` is a whole button's prop surface; these five are what the desk means by an action.
const ACTION_OPTIONS = ["label", "variant", "theme", "icon", "onClick"];

// Curated three layers deep: the options, the nested actions, and the object each callback receives.
export function openNarrowedDialog(
	verb: "confirm" | "danger",
	args: DialogConfirmOptions,
	host: NarrowedDialogHost
): Promise<true | null> {
	const options = pick(host, args, verb === "danger" ? DANGER_OPTIONS : CONFIRM_OPTIONS);
	return new Promise((resolve) => {
		let handle: { close: () => void } | null = null;
		let settled = false;
		const settle = (result: true | null) => {
			if (settled) return;
			settled = true;
			untrack();
			resolve(result);
		};
		// Closing from outside skips frappe-ui's `onCancel`, so the promise is settled here, not in that callback.
		const untrack = host.track(() => {
			handle?.close();
			settle(null);
		});
		handle = frappeDialog[verb]({
			...options,
			actions: args.actions?.map((action) => ({
				...pick(host, action, ACTION_OPTIONS, ` on action '${action.label}'`),
				onClick: async (control: any) => {
					// An action with no `onClick` is frappe-ui's plain dismiss button;
					// answering `true` for it would read as a confirmation.
					const onClick = action.onClick;
					if (!onClick) return settle(null);
					await host.hold(() => onClick(controlFor(control)));
					settle(true);
				},
			})),
			onConfirm: async (control: any) => {
				await host.hold(() => args.onConfirm?.(controlFor(control)));
				settle(true);
			},
			onCancel: async () => {
				try {
					await host.hold(() => args.onCancel?.());
				} catch (exception) {
					host.failed(exception);
				} finally {
					settle(null);
				}
			},
		} as any);
	});
}

/** Keeps the named keys and drops the rest, saying which it dropped. */
function pick(host: NarrowedDialogHost, from: object, named: string[], where = "") {
	const kept: Record<string, any> = {};
	for (const [key, value] of Object.entries(from)) {
		if (named.includes(key)) kept[key] = value;
		else
			host.warn(`with '${key}'${where}, which it does not forward — dropped. See frontend/COMPATIBILITY.md.`);
	}
	return kept;
}

// The desk's own object, not frappe-ui's `DialogControl`: a rename underneath must not change a stored script.
function controlFor(control: any): DialogControl {
	return {
		close: () => control?.close?.(),
		setError: (message) => control?.setError?.(message),
	};
}
