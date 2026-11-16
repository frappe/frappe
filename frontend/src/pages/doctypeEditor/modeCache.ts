import type { EditorState } from "./editorSource";
import type { EditorMode } from "./pendingEdits";

type Load = (doctype: string, mode?: EditorMode) => Promise<EditorState>;

/** The open DocType's loads, one per mode: a switch back reuses its load; a write drops them. */
export class ModeCache {
	private doctype = "";
	private states = new Map<EditorMode, EditorState>();

	constructor(private load: Load) {}

	/** A copy, so edits on the open canvas never reach the cached load. */
	async get(doctype: string, mode?: EditorMode): Promise<EditorState> {
		if (doctype !== this.doctype) this.drop(doctype);
		const held = mode && this.states.get(mode);
		if (held) return structuredClone(held);
		const loaded = await this.load(doctype, mode);
		if (doctype === this.doctype) this.states.set(loaded.mode, structuredClone(loaded));
		return loaded;
	}

	/** A save in one mode changes what the other shows, so both load again. */
	refresh(doctype: string, mode: EditorMode): Promise<EditorState> {
		this.drop(doctype);
		return this.get(doctype, mode);
	}

	drop(doctype: string) {
		this.doctype = doctype;
		this.states.clear();
	}
}
