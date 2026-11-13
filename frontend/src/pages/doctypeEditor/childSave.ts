// The calls one Save sends when child tables have edits: a saved child first, in its own call; a
// new child inside the parent's call, which inserts it before the parent.
import type { LayoutTree } from "@/recordPage/formLayoutSource/types";
import type { SaveError } from "./designCanvas";
import type { FlatEdit } from "./editorModel";
import type { EditorState } from "./editorSource";
import type { BaseVersion, PendingEditsPayload } from "./pendingEdits";

export const SAVE_METHOD = "frappe.desk.doctype_editor.save.save_doctype_editor";
export const CREATE_METHOD = "frappe.desk.doctype_editor.create.create_doctype";

/** A child table's staged edits; `base_version` only for a saved child. */
export interface ChildSave {
	doctype: string;
	edits: FlatEdit[];
	base_version?: BaseVersion;
}

export interface SaveCall {
	method: string;
	args: Record<string, unknown>;
	/** The child table this call saves; absent for the parent's call. */
	child?: string;
}

interface ParentSave {
	state: EditorState;
	payload: PendingEditsPayload;
	/** A new DocType's Details layout, which its first save inserts. */
	layout: LayoutTree;
}

export function saveCalls(parent: ParentSave, children: ChildSave[]): SaveCall[] {
	const { state, payload, layout } = parent;
	const saved = children.filter((child) => child.base_version);
	const added = children.filter((child) => !child.base_version);
	const calls: SaveCall[] = saved.map((child) => ({
		method: SAVE_METHOD,
		args: { doctype: child.doctype, mode: payload.mode, base_version: child.base_version, edits: child.edits },
		child: child.doctype,
	}));
	const edits = added.length
		? Object.fromEntries([[state.doctype, payload.edits], ...added.map((child) => [child.doctype, child.edits])])
		: payload.edits;
	if (state.pending) {
		calls.push({ method: CREATE_METHOD, args: { definition: state.definition, layout, edits } });
	} else if (payload.edits.length || added.length || !saved.length) {
		calls.push({ method: SAVE_METHOD, args: { ...payload, edits } });
	}
	return calls;
}

/** The child table a refused call's errors belong to, if any. */
export function refusedChild(call: SaveCall, errors: SaveError[] = []): string | undefined {
	return call.child ?? (errors as (SaveError & { doctype?: string })[]).find((error) => error.doctype)?.doctype;
}
