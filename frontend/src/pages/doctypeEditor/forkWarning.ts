// Customize's warning before an edit gives a layout type its first site layout: asked once per
// type in an editor session, and only a Continue counts as asked.
import type { FormLayoutType } from "@/recordPage/formLayoutSource/types";
import { __ } from "@/i18n";
import type { WorkingState } from "./editorModel";
import { typeLabel } from "./layoutMenu";
import { forked, type LayoutsHolder } from "./workingLayouts";

export class ForkWarning {
	private asked = new Set<FormLayoutType>();

	/** `confirm` resolves `true` to go on with the edit. */
	constructor(private confirm: (type: FormLayoutType) => Promise<boolean>) {}

	/** The types an edit from `before` to `after` forks that this session has not asked about. */
	unasked(before: WorkingState, after: WorkingState): FormLayoutType[] {
		if (after.mode !== "Customize") return [];
		return forkedTypes(before, after).filter((type) => !this.asked.has(type));
	}

	/** Asks about each type in turn; the first Cancel stops. */
	async ask(types: FormLayoutType[]): Promise<boolean> {
		for (const type of types) {
			if (!(await this.confirm(type))) return false;
			this.asked.add(type);
		}
		return true;
	}
}

/** The types that have a site row in `after` and none in `before`. */
export function forkedTypes(before: LayoutsHolder, after: LayoutsHolder): FormLayoutType[] {
	const types = Object.keys(after.layouts) as FormLayoutType[];
	return types.filter((type) => !forked(before, type) && forked(after, type));
}

export function forkWarningText(working: WorkingState, type: FormLayoutType): { title: string; message: string } {
	const label = typeLabel(type);
	const replaces = working.layouts[type]?.app.length
		? __("Saving creates a site layout for {0} that replaces the app layout on this site.", [label])
		: __("Saving creates a site layout for {0} that replaces the layout made from the DocType's fields.", [label]);
	const rows = __("Every {0} layout becomes a site layout, and later changes from the app do not reach them.", [label]);
	return { title: __("Saving creates a site layout"), message: `${replaces} ${rows}` };
}
