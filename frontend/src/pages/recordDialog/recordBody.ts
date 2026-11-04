// The body a `pages.json` dialog entry names, loaded when the dialog opens: a page's `component`, as
// for a replacement page. A body that fails to load gives way to the form, so the record stays editable.
import { defineAsyncComponent, type Component } from "vue";
import { pageOf } from "@/router/mainPage";

export function recordBodyComponent(
	loader: () => Promise<unknown>,
	failed: (error: unknown) => void
): Component {
	return defineAsyncComponent({
		loader: () =>
			loader()
				.then((module) => pageOf(module as Component))
				.catch((error) => {
					failed(error);
					return { render: () => null };
				}),
		delay: 0,
	});
}

/** A `⋯` row a body adds: frappe-ui's menu option keys. */
export interface RecordBodyAction {
	label: string;
	icon?: string;
	onClick: () => unknown;
}

/** A header icon button: the label is its tooltip and accessible name. */
export interface RecordBodyButton extends RecordBodyAction {
	icon: string;
}

/** What a body sets through its `header` prop while it shows. */
export interface RecordBodyHeader {
	/** Drawn in place of the record's name. */
	title?: string;
	/** Icon buttons left of `⋯`; the label is the tooltip. */
	buttons?: RecordBodyButton[];
	/** Rows above Copy link and Delete in `⋯`. */
	menu?: RecordBodyAction[];
	/** `false` hides Save, for a body that edits nothing itself. */
	save?: boolean;
}
