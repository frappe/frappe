// One binding's draft in an open pane: its fresh read, its saves one at a time, and each row's
// save mark. Every block bound to the same doctype and name shares it.
import { reactive } from "vue";
import {
	createDocument,
	getDocument,
	isApiError,
	updateDocument,
	type DocumentRecord,
	type Envelope,
	type FieldError as RefusedField,
} from "@framework/ui/api";
import { evaluateDependsOn } from "@framework/ui/FormLayout";
import { fieldErrorKey, fieldnameOfErrorKey, type FieldAddress } from "@framework/ui/fields/types";
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import { useDoctypeMeta, type DoctypeMeta } from "@framework/ui/useDoctypeMeta";
import { fetchNewDocument, fieldDefaults } from "@/newRecordValues";
import { FieldErrors } from "@/recordPage";
import { runAfterSave } from "@/afterSave";
import type { Confirm } from "../record/discardChanges";
import { awaitMeta } from "../record/metaSource";
import { mergeRefetch, sameContent } from "../record/refetchMerge";
import { changedFields, confirmConflict, stripTags } from "../record/saveResponse";

export type RowMark = "saving" | "saved" | "error";

type Values = Record<string, any>;

/** What a draft asks of its open pane. */
export interface DraftHost {
	confirm: Confirm;
	/** True once the pane has closed; a save still in flight then reports its failure here. */
	closed: () => boolean;
	lost: () => void;
}

const SAVED_MARK_FOR = 2500;

export class BindingDraft {
	readonly state = reactive({
		doc: {} as Values,
		saved: {} as Values,
		meta: null as DoctypeMeta | null,
		childMetas: {} as Record<string, RawMetaField[]>,
		loading: true,
		failed: "",
		isNew: false,
		marks: {} as Record<string, RowMark>,
	});
	readonly fieldErrors = new FieldErrors();
	readonly loaded: Promise<void>;
	private queued = new Set<string>();
	/** Each field a save in flight carries, with the value it sent. */
	private sending = new Map<string, unknown>();
	/** Fields a hold marked while a save was out; that save's refusal keeps their marks even when set back. */
	private heldMeanwhile = new Set<string>();
	/** The message keys those holds drew; an older refusal on the same field is not one of them. */
	private heldKeys = new Set<string>();
	/** Unsent fields found changed elsewhere since their edit; their own save asks first. */
	private stale = new Set<string>();
	private running: Promise<void> | null = null;

	constructor(
		readonly doctype: string,
		readonly name: string,
		private single: boolean,
		private host: DraftHost
	) {
		this.loaded = this.load();
	}

	dirty(fieldname: string): boolean {
		return !sameContent(this.state.doc[fieldname], this.state.saved[fieldname]);
	}

	/** Changed fields no save holds: a `button` block's edits, or an autosave that failed. */
	unsaved(fieldnames: string[]): string[] {
		return fieldnames.filter(
			(fieldname) =>
				!this.queued.has(fieldname) &&
				(this.sending.has(fieldname)
					? !sameContent(this.sending.get(fieldname), this.state.doc[fieldname])
					: this.dirty(fieldname))
		);
	}

	/** An unchanged value is no edit: frappe-ui's inputs send it again on `change`, after the commit's hold drew its message. */
	edit(fieldname: string, value: unknown) {
		if (sameContent(this.state.doc[fieldname], value)) return;
		this.state.doc[fieldname] = value;
		this.fieldErrors.clear(fieldname);
		if (!this.dirty(fieldname) && this.state.marks[fieldname] === "error")
			delete this.state.marks[fieldname];
	}

	clearReverted(fieldnames: string[]) {
		for (const fieldname of fieldnames) {
			if (this.state.marks[fieldname] !== "error" || this.dirty(fieldname)) continue;
			if (this.sending.has(fieldname)) continue;
			delete this.state.marks[fieldname];
			this.unmark(fieldname);
		}
	}

	/** Queues the changed fields, and any field a save in flight carries; that save is followed by one more. */
	save(fieldnames: string[]): Promise<void> {
		for (const fieldname of fieldnames) {
			if (!this.dirty(fieldname) && !this.sending.has(fieldname)) continue;
			this.queued.add(fieldname);
			this.state.marks[fieldname] = "saving";
		}
		this.running ??= this.drain().finally(() => (this.running = null));
		return this.running;
	}

	/** Marks fields not saved without sending them, as a missing mandatory value does. */
	hold(fieldnames: string[], refusals: { address: FieldAddress; message: string }[]) {
		for (const { address, message } of refusals) this.fieldErrors.mark(address, message);
		for (const fieldname of fieldnames) this.state.marks[fieldname] = "error";
		if (!this.sending.size) return;
		for (const fieldname of fieldnames) this.heldMeanwhile.add(fieldname);
		for (const { address } of refusals) {
			const key = fieldErrorKey(address);
			this.heldKeys.add(key);
			this.heldMeanwhile.add(fieldnameOfErrorKey(key));
		}
	}

	discard(fieldnames: string[]) {
		for (const fieldname of fieldnames) {
			this.state.doc[fieldname] = clone(this.state.saved[fieldname]);
			this.stale.delete(fieldname);
			delete this.state.marks[fieldname];
			this.unmark(fieldname);
		}
	}

	private async load() {
		try {
			const source = useDoctypeMeta(this.doctype);
			const [meta, document] = await Promise.all([awaitMeta(source), this.read()]);
			this.state.meta = meta;
			this.state.childMetas = Object.fromEntries(
				Object.entries(source.metas.value).flatMap(([doctype, child]) =>
					child.fields ? [[doctype, child.fields]] : []
				)
			);
			this.reset(document ?? (await this.newDocument(meta)));
			this.state.isNew = !document;
		} catch (error) {
			this.state.failed = messageOf(error);
		} finally {
			this.state.loading = false;
		}
	}

	/** Null for a Record that does not exist yet; a Single always reads. */
	private async read(): Promise<Values | null> {
		try {
			return (await getDocument(this.doctype, this.name)).data;
		} catch (error) {
			if (!this.single && isApiError(error) && error.status === 404) return null;
			throw error;
		}
	}

	private async newDocument(meta: DoctypeMeta): Promise<Values> {
		const defaults = fieldDefaults(await fetchNewDocument(this.doctype), meta);
		return { ...defaults, [nameField(meta)]: this.name };
	}

	private async drain() {
		while (this.queued.size) {
			const fieldnames = [...this.queued].filter((fieldname) => this.dirty(fieldname));
			for (const fieldname of this.queued)
				if (!fieldnames.includes(fieldname)) delete this.state.marks[fieldname];
			this.queued.clear();
			if (!fieldnames.length) continue;
			for (const fieldname of this.withRequired(fieldnames))
				this.sending.set(fieldname, clone(this.state.doc[fieldname]));
			try {
				await this.send(fieldnames);
			} finally {
				this.sending.clear();
				this.heldMeanwhile.clear();
				this.heldKeys.clear();
			}
		}
	}

	private withRequired(fieldnames: string[]): string[] {
		if (!this.state.isNew) return fieldnames;
		const { doc, saved, meta } = this.state;
		const required = (meta?.fields ?? [])
			.filter((field) => isRequired(field, doc))
			.map(({ fieldname }) => fieldname)
			.filter((fieldname) => isEmpty(saved[fieldname]) && !isEmpty(doc[fieldname]));
		return [...new Set([...fieldnames, ...required])];
	}

	private async send(fieldnames: string[]) {
		if (fieldnames.some((fieldname) => this.stale.has(fieldname)))
			return this.resolveConflict(fieldnames, null);
		const values = Object.fromEntries(
			[...this.sending].map(([fieldname, value]) => [fieldname, clone(value)])
		);
		try {
			const reply = (await this.write(values)).data;
			this.land(reply, values);
			this.settle(fieldnames, "saved");
			this.settleAdded(fieldnames);
			runAfterSave({ doctype: this.doctype, name: this.name, doc: reply, changed: Object.keys(values) });
		} catch (error) {
			if (isApiError(error) && error.isTimestampMismatch)
				await this.resolveConflict(fieldnames, error);
			else this.refuse(fieldnames, error);
		}
	}

	private write(values: Values) {
		if (this.state.isNew)
			return createDocument(this.doctype, { ...values, [nameField(this.state.meta!)]: this.name });
		const body = { ...values, modified: this.state.saved.modified } as DocumentRecord;
		return updateDocument(this.doctype, this.name, body);
	}

	/** The reply is the saved copy; a field changed again while the save was out keeps its new value. */
	private land(reply: Values, sent: Values) {
		const { doc, saved } = mergeRefetch(
			{ doc: this.state.doc, saved: { ...this.state.saved, ...sent } },
			reply
		);
		replace(this.state.saved, { ...saved, modified: reply.modified });
		replace(this.state.doc, { ...doc, modified: reply.modified });
		this.state.isNew = false;
	}

	private settleAdded(fieldnames: string[]) {
		for (const fieldname of this.sending.keys()) {
			if (fieldnames.includes(fieldname) || this.dirty(fieldname)) continue;
			delete this.state.marks[fieldname];
			this.unmark(fieldname);
		}
	}

	/** Sent again with the new `modified` when the other save left these fields alone; else the reader chooses, and Reload sends the rest. */
	private async resolveConflict(fieldnames: string[], refusal: unknown) {
		let latest: Envelope<Values>;
		try {
			latest = await getDocument(this.doctype, this.name, { include: ["users"] });
		} catch (error) {
			return this.refuse(fieldnames, error);
		}
		const fresh = latest.data;
		const users = latest.users as Record<string, { full_name?: string }> | undefined;
		const touched = (fieldname: string) =>
			this.stale.has(fieldname) || !sameContent(fresh[fieldname], this.state.saved[fieldname]);
		const conflicting = fieldnames.filter(
			(fieldname) => touched(fieldname) && !sameContent(this.state.doc[fieldname], fresh[fieldname])
		);
		if (!conflicting.length) {
			if (refusal && fresh.modified === this.state.saved.modified) return this.refuse(fieldnames, refusal);
			this.adopt(fresh, touched);
			for (const fieldname of fieldnames) this.queued.add(fieldname);
			return;
		}
		this.settle(fieldnames, "error");
		if (this.host.closed()) return this.host.lost();
		const editor = users?.[fresh.modified_by]?.full_name || fresh.modified_by;
		const changed = changedFields(
			pick(this.state.doc, conflicting),
			pick(this.state.saved, conflicting),
			this.state.meta?.fields
		);
		if (!(await confirmConflict(this.host.confirm, editor, changed))) return;
		this.discard(conflicting);
		this.adopt(fresh, touched);
		for (const fieldname of fieldnames.filter((fieldname) => !conflicting.includes(fieldname))) {
			this.queued.add(fieldname);
			this.state.marks[fieldname] = "saving";
		}
	}

	/** Takes the newer copy under the reader's edits; one the other save also changed asks before its own save. */
	private adopt(fresh: Values, touched: (fieldname: string) => boolean) {
		for (const fieldname of Object.keys(this.state.doc))
			if (this.dirty(fieldname) && touched(fieldname)) this.stale.add(fieldname);
		const { doc, saved } = mergeRefetch(this.state, fresh);
		replace(this.state.saved, { ...saved, modified: fresh.modified });
		replace(this.state.doc, { ...doc, modified: fresh.modified });
		for (const fieldname of this.stale) if (!this.dirty(fieldname)) this.stale.delete(fieldname);
	}

	/** A field set back before the reply landed keeps no refusal, and a hold placed meanwhile stays. */
	private refuse(fieldnames: string[], error: unknown) {
		const sent = [...this.sending.keys()];
		const refusals = (isApiError(error) && error.fieldErrors) || [];
		const named = refusals.map((refused) => refused.parentfield ?? refused.fieldname);
		const failed = sent.filter(
			(fieldname) => (fieldnames.includes(fieldname) || named.includes(fieldname)) && this.dirty(fieldname)
		);
		const setBack = sent.filter((fieldname) => !this.dirty(fieldname));
		if (refusals.length)
			this.fieldErrors.markRefused(
				refusals.filter((refused) => !this.quiet(refused, setBack)),
				this.state.doc
			);
		else
			for (const fieldname of failed)
				if (!this.holdsUnder(fieldname)) this.fieldErrors.mark(fieldname, messageOf(error));
		for (const fieldname of setBack) {
			if (this.heldMeanwhile.has(fieldname)) continue;
			this.unmark(fieldname);
			if (!this.queued.has(fieldname)) delete this.state.marks[fieldname];
		}
		this.settle(failed, "error");
		if (sent.some((fieldname) => this.dirty(fieldname)) && this.host.closed()) this.host.lost();
	}

	private quiet(refused: RefusedField, setBack: string[]): boolean {
		const fieldname = refused.parentfield ?? refused.fieldname;
		if (!this.sending.has(fieldname)) return false;
		if (setBack.includes(fieldname)) return true;
		const address = this.fieldErrors.addressOf(refused, this.state.doc);
		return !!address && this.holds(fieldErrorKey(address));
	}

	/** Only while the hold's message is still drawn: an edit, or a component's own change, may have cleared it. */
	private holds(key: string): boolean {
		return this.heldKeys.has(key) && key in this.fieldErrors.drawn.value;
	}

	/** A message with no field lands on the table itself, so a held cell keeps it off. */
	private holdsUnder(fieldname: string): boolean {
		return [...this.heldKeys].some((key) => fieldnameOfErrorKey(key) === fieldname && this.holds(key));
	}

	/** A field queued again keeps Saving…, and one changed since it was sent keeps its hold or none; Saved fades on its own. */
	private settle(fieldnames: string[], mark: RowMark) {
		for (const fieldname of fieldnames) {
			if (this.queued.has(fieldname)) continue;
			if (mark === "saved" && this.dirty(fieldname)) {
				if (this.state.marks[fieldname] === "error") continue;
				delete this.state.marks[fieldname];
				this.unmark(fieldname);
				continue;
			}
			this.state.marks[fieldname] = mark;
			if (mark !== "saved") continue;
			this.unmark(fieldname);
			setTimeout(() => {
				if (this.state.marks[fieldname] === "saved") delete this.state.marks[fieldname];
			}, SAVED_MARK_FOR);
		}
	}

	/** The field's own mark, and the marks on its rows' cells when it is a table. */
	private unmark(fieldname: string) {
		this.fieldErrors.unmark(fieldname);
		for (const key of Object.keys(this.fieldErrors.drawn.value))
			if (fieldnameOfErrorKey(key) === fieldname) this.fieldErrors.unmark(key);
	}

	private reset(document: Values) {
		this.stale.clear();
		replace(this.state.saved, clone(document));
		replace(this.state.doc, clone(document));
		this.state.marks = {};
		this.fieldErrors.clearAll();
	}
}

/** The field a record's name comes from: `<f>` for `field:<f>` naming, else `name`. */
function nameField(meta: DoctypeMeta): string {
	return meta.autoname?.startsWith("field:") ? meta.autoname.slice("field:".length).trim() : "name";
}

function messageOf(error: unknown): string {
	return stripTags(error instanceof Error ? error.message : String(error));
}

function isRequired(field: RawMetaField, doc: Values): boolean {
	return !!field.reqd || (!!field.mandatory_depends_on && evaluateDependsOn(field.mandatory_depends_on, doc));
}

function isEmpty(value: unknown): boolean {
	return Array.isArray(value) ? value.length === 0 : value == null || value === "";
}

function pick(values: Values, fieldnames: string[]): Values {
	return Object.fromEntries(fieldnames.map((fieldname) => [fieldname, values[fieldname]]));
}

/** In place, so a component that kept `doc` or `saved` keeps the live object. */
function replace(target: Values, values: Values) {
	for (const key of Object.keys(target)) if (!(key in values)) delete target[key];
	Object.assign(target, values);
}

function clone<T>(value: T): T {
	return value === undefined ? value : JSON.parse(JSON.stringify(value));
}
