import { ref, shallowRef } from "vue";
import { toast } from "frappe-ui";
import { runMethod } from "@framework/ui/api";
import { __, __n } from "@/i18n";
import { errorMessage } from "@/recordPage/errorMessage";
import { CREATE_METHOD, errorsByDoctype, SAVE_METHOD, saveCalls, type SaveCall } from "./childSave";
import type { ChildTables } from "./childTables";
import type { DesignCanvas, SaveError } from "./designCanvas";
import { EditRefused, fieldsOffLayout } from "./editorModel";
import type { BaseVersion, Edit, PendingEdits } from "./pendingEdits";

export type SaveOffer = "editor.reload_and_reapply" | "editor.write_files_again" | "editor.open_list";

/** What the banner over the canvas says after a save; `doctype` keeps it to that DocType's editor. */
export interface SaveBanner {
	doctype: string;
	title: string;
	messages: string[];
	offers: SaveOffer[];
	failed: boolean;
}

interface SaveResult {
	saved: boolean;
	base_version?: BaseVersion;
	errors?: SaveError[];
	/** The DocTypes a failed save had already written. */
	written?: string[];
	doctype?: string;
}

/** The realtime `doctype_export` message: how the file export after a save went. */
export interface ExportResult {
	doctype: string;
	ok: boolean;
	error?: string | null;
	app_layouts?: Record<string, string>;
}

export interface SaveHost {
	edits: PendingEdits;
	canvas: () => DesignCanvas | null;
	/** Loads the DocType again with no edits staged; its new canvas, or null once the page moved on. */
	reload: () => Promise<DesignCanvas | null>;
	/** A new DocType's first save made it: its own editor opens in place of `/doctype/new`, unless the page moved on. */
	created: (doctype: string) => Promise<DesignCanvas | null>;
	/** The page's child tables, whose staged edits save with the parent's. */
	children?: Pick<ChildTables, "saves" | "saved" | "loaded" | "canvasOf" | "clearErrors">;
	/** Opens a child table's editor, to mark its refused edits there. */
	showChild?: (doctype: string) => Promise<DesignCanvas | null>;
}

export { CREATE_METHOD, SAVE_METHOD };
export const WRITE_FILES_METHOD = "frappe.core.doctype.doctype.doctype.write_doctype_files";

export class EditorSave {
	readonly saving = ref(false);
	readonly banner = shallowRef<SaveBanner | null>(null);
	/** An export that lands while a save or reload runs waits for it: that reload would race this one. */
	private lateExport: ExportResult | null = null;

	constructor(private host: SaveHost) {}

	offers(offer: SaveOffer): boolean {
		return Boolean(this.banner.value?.offers.includes(offer));
	}

	async save() {
		const canvas = this.host.canvas();
		if (!canvas || this.saving.value) return;
		this.banner.value = null;
		canvas.errors.value = [];
		this.host.children?.clearErrors();
		await this.busy(async () => {
			const { result, call } = await this.send(canvas);
			if (call) await this.refused(canvas, result, call);
			else await this.saved(canvas, result);
		});
	}

	/** Loads the DocType as it is now and stages each undo step again; the ones it refuses are listed. */
	async reloadAndReapply() {
		if (this.saving.value) return;
		const steps = this.host.edits.steps;
		await this.busy(async () => {
			const canvas = await this.host.reload();
			if (canvas) await this.reapply(canvas, steps);
		});
	}

	private async reapply(canvas: DesignCanvas, steps: readonly Edit[][]) {
		// The replay is the reload's own staging, so it runs before any late export reloads again.
		this.host.edits.locked.value = false;
		const refused: string[] = [];
		for (const step of steps) {
			const doctype = step[0].doctype;
			try {
				const target = doctype ? await this.host.children!.loaded(doctype) : canvas;
				target.stage(...step.map(({ act, value }) => ({ ...value, act })));
			} catch (error) {
				if (!(error instanceof EditRefused)) throw error;
				refused.push(__(error.template, error.args));
			}
		}
		this.banner.value = refused.length
			? {
					doctype: canvas.state.doctype,
					title: __n(
						"{0} edit could not be applied again",
						"{0} edits could not be applied again",
						refused.length,
						[refused.length],
					),
					messages: refused,
					offers: [],
					failed: true,
				}
			: null;
	}

	async writeFilesAgain() {
		const canvas = this.host.canvas();
		if (!canvas) return;
		const { data } = await runMethod<Record<string, string>>(
			WRITE_FILES_METHOD,
			{ doctype: canvas.state.doctype },
			{ nullable: true },
		);
		if (data) this.rebaseAppLayouts(data);
		this.banner.value = null;
		toast.success(__("Files written"));
	}

	/** The export runs after the save's response, so its outcome comes later, by realtime. */
	async exported(result: ExportResult) {
		const canvas = this.host.canvas();
		if (!canvas || result.doctype !== canvas.state.doctype) return;
		if (this.saving.value) return void (this.lateExport = result);
		if (result.ok) return this.reloadExported(result);
		this.banner.value = {
			doctype: result.doctype,
			title: __("Saved, but the DocType's files were not written"),
			messages: result.error ? [result.error] : [],
			offers: ["editor.write_files_again"],
			failed: true,
		};
	}

	/** The save's reload read the layouts before the export wrote them; with no edits staged, read them again. */
	private async reloadExported(result: ExportResult) {
		if (!this.host.edits.dirty.value) return void (await this.host.reload());
		if (result.app_layouts) this.rebaseAppLayouts(result.app_layouts);
	}

	/** Save and Reload hold Save and every edit until they finish; a late export runs after. */
	private async busy<T>(run: () => Promise<T>): Promise<T> {
		this.saving.value = true;
		this.host.edits.locked.value = true;
		try {
			return await run();
		} finally {
			this.saving.value = false;
			this.host.edits.locked.value = false;
			const late = this.lateExport;
			this.lateExport = null;
			if (late) void this.exported(late).catch((error) => toast.error(errorMessage(error)));
		}
	}

	/** Sends each call in order and stops at the first refused one; the children saved before it leave the stack. */
	private async send(canvas: DesignCanvas): Promise<{ result: SaveResult; call?: SaveCall }> {
		const parent = { state: canvas.state, payload: this.host.edits.payload(), layout: canvas.base.layout };
		const written: string[] = [];
		let result: SaveResult = { saved: true };
		for (const call of saveCalls(parent, this.host.children?.saves() ?? [])) {
			({ data: result } = await runMethod<SaveResult>(call.method, call.args));
			if (!result.saved) {
				for (const child of written) await this.host.children?.saved(child);
				return { result: { ...result, written: [...written, ...(result.written ?? [])] }, call };
			}
			if (call.child) written.push(call.child);
		}
		return { result };
	}

	private async saved(canvas: DesignCanvas, result: SaveResult) {
		const asked = fieldsOffLayout(canvas.working.value)
			.filter(({ field }) => field.reqd)
			.map(({ field }) => field.fieldname);
		if (!canvas.state.pending) {
			const next = await this.host.reload().catch((error) => {
				// The save is in: never replay its edits on a canvas that failed to reload.
				this.host.edits.clear();
				if (result.base_version) this.host.edits.rebase(result.base_version);
				throw error;
			});
			if (next) next.askedOnSave.value = asked;
			return void toast.success(__("Saved"));
		}
		const doctype = result.doctype ?? canvas.state.doctype;
		const next = await this.host.created(doctype);
		if (!next) return void toast.success(__("{0} is created.", [doctype]));
		next.askedOnSave.value = asked;
		this.banner.value = {
			doctype,
			title: __("{0} is created.", [doctype]),
			messages: [],
			offers: ["editor.open_list"],
			failed: false,
		};
	}

	/** Each refused DocType's errors draw on its own canvas; the first refused child's editor opens. */
	private async refused(canvas: DesignCanvas, result: SaveResult, call: SaveCall) {
		const errors = errorsByDoctype(call, canvas.state.doctype, result.errors);
		const child = [...errors.keys()].find((doctype) => doctype !== canvas.state.doctype);
		const shown = (child && (await this.host.showChild?.(child))) || canvas;
		const targets = new Map<DesignCanvas, SaveError[]>();
		for (const [doctype, own] of errors) {
			const target = doctype === shown.state.doctype ? shown : (this.host.children?.canvasOf(doctype) ?? canvas);
			targets.set(target, [...(targets.get(target) ?? []), ...own]);
		}
		const marked = [...targets].map(([target, own]) => markErrors(target, own));
		const messages = marked.flatMap(({ unmarked }) => unmarked);
		if (marked.some(({ placed }) => placed) && !messages.length) {
			messages.push(__("Fix what is marked on the form, then save again."));
		}
		const written = result.written ?? [];
		if (written.length) {
			messages.push(__("Part of the save is written: {0}. Reload to see it.", [written.join(", ")]));
		}
		const stale = (result.errors ?? []).some((error) => error.code === "stale");
		this.banner.value = {
			doctype: shown.state.doctype,
			title: __("Not saved"),
			messages,
			offers: stale || written.length ? ["editor.reload_and_reapply"] : [],
			failed: true,
		};
	}

	private rebaseAppLayouts(appLayouts: Record<string, string>) {
		const { base_version } = this.host.edits.payload();
		this.host.edits.rebase({ ...base_version, app_layouts: { ...base_version.app_layouts, ...appLayouts } });
	}
}

/** Draws the errors on `canvas` and selects the first marked field; the ones it cannot draw go to the banner. */
function markErrors(canvas: DesignCanvas, errors: SaveError[]): { placed: boolean; unmarked: string[] } {
	canvas.errors.value = errors;
	const marked = errors.filter((error) => marks(canvas, error));
	const first = marked.find((error) => error.target.kind === "field");
	if (first) canvas.select({ kind: "field", fieldname: first.target.fieldname! });
	const unmarked = errors.filter((error) => !marked.includes(error)).map((error) => error.message);
	return { placed: marked.length > 0, unmarked };
}

/** A field or section error the canvas draws at its target; the rest go to the banner. */
function marks(canvas: DesignCanvas, error: SaveError): boolean {
	const { kind, fieldname, container } = error.target;
	if (kind === "field") return Boolean(fieldname && canvas.field(fieldname));
	if (kind !== "container" || !container) return false;
	// Column names repeat across sections, so only a section shows its error in place.
	return canvas.tabs.value.some((tab) => tab.sections.some((section) => section.name === container));
}
