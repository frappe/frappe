// What the switcher needs of the page that holds it.
import type { ViewType } from "./viewMenu";

export interface SwitcherHost {
	doctype: string;
	app: string;
	/** The open view; `plainModified` is true for a plain view with changes. */
	view: () => { key: string; label: string; plainModified: boolean };
	admin: boolean;
	types: ViewType[];
	unbuilt: ViewType[];
	/** True while the page draws the act, by its short name (`rename_view`). */
	drawn: (act: string) => boolean;
	/** A menu row's act: a refusal is toasted. */
	run: (act: string, value?: unknown) => void;
	/** A dialog's act: a refusal rejects, so the dialog can say why. */
	call: (act: string, value?: unknown) => Promise<unknown>;
}
