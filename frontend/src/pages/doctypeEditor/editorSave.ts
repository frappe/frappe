// The editor's save: the pending edits to `save_doctype_editor`, or a new DocType's first save to
// `create_doctype`; then what a refused, stale or half-written save offers next.
import { ref, shallowRef } from "vue";
import { toast } from "frappe-ui";
import { runMethod } from "@framework/ui/api";
import { __, __n } from "@/i18n";
import type { DesignCanvas, SaveError } from "./designCanvas";
import { EditRefused, fieldsOffLayout, type FlatEdit } from "./editorModel";
import type { BaseVersion, PendingEdits } from "./pendingEdits";

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
	/** Loads the DocType again with no edits staged; its new canvas. */
	reload: () => Promise<DesignCanvas>;
	/** A new DocType's first save made it: its own editor opens in place of `/doctype/new`. */
	created: (doctype: string) => Promise<DesignCanvas>;
}

export const SAVE_METHOD = "frappe.desk.doctype_editor.save.save_doctype_editor";
export const CREATE_METHOD = "frappe.desk.doctype_editor.create.create_doctype";
export const WRITE_FILES_METHOD = "frappe.core.doctype.doctype.doctype.write_doctype_files";

export class EditorSave {
	readonly saving = ref(false);
	readonly banner = shallowRef<SaveBanner | null>(null);

	constructor(private host: SaveHost) {}

	offers(offer: SaveOffer): boolean {
		return Boolean(this.banner.value?.offers.includes(offer));
	}

	async save() {
		const canvas = this.host.canvas();
		if (!canvas || this.saving.value) return;
		this.saving.value = true;
		this.banner.value = null;
		canvas.errors.value = [];
		try {
			const result = await this.send(canvas);
			if (result.saved) await this.saved(canvas, result);
			else this.refused(canvas, result);
		} finally {
			this.saving.value = false;
		}
	}

	/** Loads the DocType as it is now and stages each undo step again; the ones it refuses are listed. */
	async reloadAndReapply() {
		const steps: FlatEdit[][] = this.host.edits.steps.map((step) =>
			step.map(({ act, value }) => ({ ...value, act })),
		);
		const canvas = await this.host.reload();
		const refused: string[] = [];
		for (const step of steps) {
			try {
				canvas.stage(...step);
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

	private async send(canvas: DesignCanvas): Promise<SaveResult> {
		const payload = this.host.edits.payload();
		const { data } = canvas.state.pending
			? await runMethod<SaveResult>(CREATE_METHOD, {
					definition: canvas.state.definition,
					layout: canvas.base.layout,
					edits: payload.edits,
				})
			: await runMethod<SaveResult>(SAVE_METHOD, { ...payload });
		return data;
	}

	private async saved(canvas: DesignCanvas, result: SaveResult) {
		const asked = fieldsOffLayout(canvas.working.value)
			.filter(({ field }) => field.reqd)
			.map(({ field }) => field.fieldname);
		if (!canvas.state.pending) {
			const next = await this.host.reload();
			next.askedOnSave.value = asked;
			return void toast.success(__("Saved"));
		}
		const doctype = result.doctype ?? canvas.state.doctype;
		const next = await this.host.created(doctype);
		next.askedOnSave.value = asked;
		this.banner.value = {
			doctype,
			title: __("{0} is created.", [doctype]),
			messages: [],
			offers: ["editor.open_list"],
			failed: false,
		};
	}

	private refused(canvas: DesignCanvas, result: SaveResult) {
		const errors = result.errors ?? [];
		canvas.errors.value = errors;
		const marked = errors.filter((error) => marks(canvas, error));
		const first = marked.find((error) => error.target.kind === "field");
		if (first) canvas.select({ kind: "field", fieldname: first.target.fieldname! });
		const messages = errors.filter((error) => !marked.includes(error)).map((error) => error.message);
		if (marked.length && !messages.length) messages.push(__("Fix what is marked on the form, then save again."));
		const written = result.written ?? [];
		if (written.length) {
			messages.push(__("Part of the save is written: {0}. Reload to see it.", [written.join(", ")]));
		}
		const stale = errors.some((error) => error.code === "stale");
		this.banner.value = {
			doctype: canvas.state.doctype,
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

/** A field or section error the canvas draws at its target; the rest go to the banner. */
function marks(canvas: DesignCanvas, error: SaveError): boolean {
	const { kind, fieldname, container } = error.target;
	if (kind === "field") return Boolean(fieldname && canvas.field(fieldname));
	if (kind !== "container" || !container) return false;
	// Column names repeat across sections, so only a section shows its error in place.
	return canvas.tabs.value.some((tab) => tab.sections.some((section) => section.name === container));
}
