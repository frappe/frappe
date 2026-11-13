// Customize's warning before an edit gives a layout type its first site layout: asked once per
// type in an editor session, and only a Continue counts as asked.
import type { FormLayoutType } from "@/recordPage/formLayoutSource/types";
import type { WorkingState } from "./editorModel";
import { forked, type LayoutsHolder } from "./workingLayouts";

export class ForkWarning {
	/** `<doctype>\n<type>`: one page opens many DocTypes. */
	private asked = new Set<string>();

	/** `confirm` resolves `true` to go on with the edit. */
	constructor(private confirm: (type: FormLayoutType) => Promise<boolean>) {}

	/** The types an edit from `before` to `after` forks that this session has not asked about. */
	unasked(before: WorkingState, after: WorkingState): FormLayoutType[] {
		if (after.mode !== "Customize") return [];
		return forkedTypes(before, after).filter((type) => !this.asked.has(`${after.doctype}\n${type}`));
	}

	/** Asks about each of `doctype`'s types in turn; the first Cancel stops. */
	async ask(doctype: string, types: FormLayoutType[]): Promise<boolean> {
		for (const type of types) {
			if (!(await this.confirm(type))) return false;
			this.asked.add(`${doctype}\n${type}`);
		}
		return true;
	}
}

/** The types that have a site row in `after` and none in `before`. */
export function forkedTypes(before: LayoutsHolder, after: LayoutsHolder): FormLayoutType[] {
	const types = Object.keys(after.layouts) as FormLayoutType[];
	return types.filter((type) => !forked(before, type) && forked(after, type));
}
