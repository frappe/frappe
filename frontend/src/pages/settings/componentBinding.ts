// What a component block gets for each named binding: the pane's shared draft, read live.
import type { DoctypeMeta } from "@framework/ui/useDoctypeMeta";
import type { BindingDraft } from "./bindingDraft";

export interface ComponentBinding {
	/** The shared draft: edit it in place, then `commit()` once a value is final. */
	readonly doc: Record<string, any>;
	readonly saved: Record<string, any>;
	readonly meta: DoctypeMeta | null;
	readonly loading: boolean;
	/** Why the binding could not be read, or "". */
	readonly error: string;
	/** A Record that does not exist yet; its first save inserts it. */
	readonly isNew: boolean;
	/** Saves the changed fields in `auto` mode; in `button` mode the Save bar does. */
	commit(): Promise<void>;
}

export function componentBinding(
	draft: BindingDraft,
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
			return state.failed;
		},
		get isNew() {
			return state.isNew;
		},
		commit,
	};
}
