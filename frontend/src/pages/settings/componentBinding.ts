// What a component block gets for each named binding: the pane's shared draft, read live.
import { fieldnameOfErrorKey } from "@framework/ui/fields/types";
import type { DoctypeMeta } from "@framework/ui/useDoctypeMeta";
import { __ } from "@/i18n";
import type { BindingDraft } from "./bindingDraft";

export interface ComponentBinding {
	/** The shared draft: edit it in place, then `commit()` once a value is final. */
	readonly doc: Record<string, any>;
	readonly saved: Record<string, any>;
	readonly meta: DoctypeMeta | null;
	readonly loading: boolean;
	/** Why the binding could not be read, or why a save of the block's own fields was refused; else "". */
	readonly error: string;
	/** A Record that does not exist yet; its first save inserts it. */
	readonly isNew: boolean;
	/** Saves the changed fields in `auto` mode; in `button` mode the Save bar does. */
	commit(): Promise<void>;
}

export function componentBinding(
	draft: BindingDraft,
	owned: () => string[],
	claimed: () => string[],
	commit: () => Promise<void>
): ComponentBinding {
	const { state } = draft;
	return {
		get doc() {
			return state.doc;
		},
		get saved() {
			return state.saved;
		},
		get meta() {
			return state.meta;
		},
		get loading() {
			return state.loading;
		},
		get error() {
			return state.failed || refusal(draft, owned(), claimed());
		},
		get isNew() {
			return state.isNew;
		},
		commit,
	};
}

/** The owned fields' errors, else, on a save that marked an owned field, a refused field no block claims. */
function refusal(draft: BindingDraft, owned: string[], claimed: string[]): string {
	const drawn = Object.entries(draft.fieldErrors.drawn.value);
	const messageOn = (matches: (fieldname: string) => boolean) => {
		const [, message] = drawn.find(([key]) => matches(fieldnameOfErrorKey(key))) ?? [];
		return message ? [message].flat().join(" ") : "";
	};
	const own = messageOn((fieldname) => owned.includes(fieldname));
	if (own) return own;
	if (!owned.some((fieldname) => draft.state.marks[fieldname] === "error")) return "";
	return messageOn((fieldname) => !claimed.includes(fieldname)) || __("Did not save");
}
