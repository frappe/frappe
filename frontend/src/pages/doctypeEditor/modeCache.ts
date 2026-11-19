import type { EditorState } from "./editorSource";
import type { EditorMode } from "./pendingEdits";

type Load = (doctype: string, mode?: EditorMode) => Promise<EditorState>;

/** The open DocType's loads, one per mode: a switch back reuses its load; a write drops them, and a load that began before it is not kept. */
export class ModeCache {
	private doctype = "";
	private generation = 0;
	/** The mode the server picked when none was asked for. */
	private picked?: EditorMode;
	private states = new Map<EditorMode, EditorState>();

	constructor(private load: Load) {}

	/** A copy, so edits on the open canvas never reach the cached load. */
	async get(doctype: string, mode?: EditorMode): Promise<EditorState> {
		if (doctype !== this.doctype) this.drop(doctype);
		const key = mode ?? this.picked;
		const held = key && this.states.get(key);
		if (held) return structuredClone(held);
		const generation = this.generation;
		const loaded = await this.load(doctype, mode);
		if (generation !== this.generation) return loaded;
		this.states.set(loaded.mode, structuredClone(loaded));
		if (!mode) this.picked = loaded.mode;
		return loaded;
	}

	/** A save in one mode changes what the other shows, so both load again. */
	refresh(doctype: string, mode: EditorMode): Promise<EditorState> {
		this.drop(doctype);
		return this.get(doctype, mode);
	}

	drop(doctype: string) {
		this.doctype = doctype;
		this.generation++;
		this.picked = undefined;
		this.states.clear();
	}
}
