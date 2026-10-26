// An open pane's drafts: one per binding, shared by every block bound to it and read fresh when
// the pane opens. `auto` blocks save on commit; the Save bar saves the `button` blocks.
import { computed, type ComputedRef } from "vue";
import { toast } from "frappe-ui";
import { layoutFields } from "@framework/ui/FormLayout";
import type { FormLayoutSchema } from "@framework/ui/FormLayout/types";
import { __ } from "@/i18n";
import { missingRequired } from "@/recordPage";
import type { SettingsBinding, SettingsBlock, SettingsPane } from "@/shell/settingsPanes";
import type { Confirm } from "../record/discardChanges";
import { BindingDraft } from "./bindingDraft";
import { blockLayout } from "./settingsRows";

/** A generated block with its draft and the fields it draws. */
export interface BoundBlock {
	block: SettingsBlock;
	draft: BindingDraft;
	layout: ComputedRef<FormLayoutSchema>;
	fieldnames: ComputedRef<string[]>;
}

export class PaneDrafts {
	readonly bound = new Map<string, BoundBlock>();
	readonly loaded: Promise<void>;
	/** How many fields the `button` blocks have changed. */
	readonly unsavedCount: ComputedRef<number>;
	/** How many `button` blocks hold a field that did not save. */
	readonly failedCount: ComputedRef<number>;
	readonly saving: ComputedRef<boolean>;
	/** Whether the pane has a `button` block, and so a Save bar to keep rows clear of. */
	readonly hasButtons: boolean;
	private isClosed = false;

	constructor(pane: SettingsPane, sessionUser: string, confirm: Confirm) {
		const drafts = new Map<string, BindingDraft>();
		const host = {
			confirm,
			closed: () => this.isClosed,
			lost: () => toast.error(__("{0} did not save", [__(pane.label)])),
		};
		for (const block of pane.blocks) {
			if (!block.binding) continue;
			const { doctype, type } = block.binding;
			const name = resolveName(block.binding, sessionUser);
			const identity = `${doctype}/${name}`;
			if (!drafts.has(identity))
				drafts.set(identity, new BindingDraft(doctype, name, type === "Single", host));
			this.bound.set(block.key, bind(block, drafts.get(identity)!));
		}
		this.loaded = Promise.all([...drafts.values()].map((draft) => draft.loaded)).then(() => {});

		const buttons = [...this.bound.values()].filter(({ block }) => block.save_mode === "button");
		this.hasButtons = buttons.length > 0;
		const marked = (bound: BoundBlock, mark: string) =>
			bound.fieldnames.value.some((fieldname) => bound.draft.state.marks[fieldname] === mark);
		this.unsavedCount = computed(
			() =>
				new Set(
					buttons.flatMap(({ draft, fieldnames }) =>
						fieldnames.value
							.filter((fieldname) => draft.dirty(fieldname))
							.map((fieldname) => `${draft.doctype}/${draft.name}/${fieldname}`)
					)
				).size
		);
		this.failedCount = computed(() => buttons.filter((bound) => marked(bound, "error")).length);
		this.saving = computed(() => buttons.some((bound) => marked(bound, "saving")));
	}

	/** An `auto` block's commit: its binding's changed `auto` fields, the ones that failed before included. */
	commit(bound: BoundBlock) {
		if (bound.block.save_mode !== "auto") return;
		const { draft } = bound;
		const fieldnames = this.fieldnamesOf(draft, "auto").filter(
			(fieldname) => draft.dirty(fieldname) || draft.state.marks[fieldname] === "saving"
		);
		this.saveOrHold(draft, fieldnames);
	}

	/** The Save bar: each binding's `button` changes, in parallel, with nothing rolled back. */
	async saveButtons() {
		const drafts = new Set([...this.bound.values()].map(({ draft }) => draft));
		await Promise.all(
			[...drafts].map((draft) =>
				this.saveOrHold(
					draft,
					this.fieldnamesOf(draft, "button").filter((fieldname) => draft.dirty(fieldname))
				)
			)
		);
	}

	discardButtons() {
		for (const { block, draft, fieldnames } of this.bound.values())
			if (block.save_mode === "button") draft.discard(fieldnames.value);
	}

	/** True while a change no save holds would be lost: a `button` edit or a failed autosave. */
	unsaved(): boolean {
		return [...this.bound.values()].some(
			({ draft, fieldnames }) => draft.unsaved(fieldnames.value).length > 0
		);
	}

	/** A save still in flight finishes; if it then fails, a toast names the pane. */
	close() {
		this.isClosed = true;
	}

	private saveOrHold(draft: BindingDraft, fieldnames: string[]) {
		if (!fieldnames.length) return;
		const missing = [...this.bound.values()]
			.filter((bound) => bound.draft === draft)
			.flatMap(({ layout }) => missingRequired(layout.value, draft.state.doc));
		if (missing.length) return draft.hold(fieldnames, missing);
		return draft.save(fieldnames);
	}

	private fieldnamesOf(draft: BindingDraft, mode: SettingsBlock["save_mode"]): string[] {
		const fieldnames = [...this.bound.values()]
			.filter(({ block, draft: other }) => other === draft && block.save_mode === mode)
			.flatMap((bound) => bound.fieldnames.value);
		return [...new Set(fieldnames)];
	}
}

function bind(block: SettingsBlock, draft: BindingDraft): BoundBlock {
	const layout = computed(() =>
		draft.state.meta ? blockLayout(block, draft.state.meta.fields ?? [], draft.state.childMetas) : []
	);
	const fieldnames = computed(() => layoutFields(layout.value).map((field) => field.fieldname));
	return { block, draft, layout, fieldnames };
}

/** A Single is named after its doctype; `session_user` names the person signed in. */
function resolveName(binding: SettingsBinding, sessionUser: string): string {
	return binding.type === "Single" ? binding.doctype : sessionUser;
}
