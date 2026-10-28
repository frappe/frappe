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
import { componentBinding, type ComponentBinding } from "./componentBinding";
import { blockLayout } from "./settingsRows";

/** A block's hold on one draft: a generated block's fields, or a component's named binding. */
export interface BoundBlock {
	block: SettingsBlock;
	draft: BindingDraft;
	layout: ComputedRef<FormLayoutSchema>;
	fieldnames: ComputedRef<string[]>;
}

type SaveMode = SettingsBlock["save_mode"];

export class PaneDrafts {
	/** The generated blocks, by key. */
	readonly bound = new Map<string, BoundBlock>();
	/** Each component block's named bindings, by block key; a block with none is not here. */
	readonly components = new Map<string, Record<string, ComponentBinding>>();
	readonly loaded: Promise<void>;
	/** How many fields the `button` blocks have changed. */
	readonly unsavedCount: ComputedRef<number>;
	/** How many `button` blocks hold a field that did not save. */
	readonly failedCount: ComputedRef<number>;
	readonly saving: ComputedRef<boolean>;
	/** Whether the pane has a `button` block, and so a Save bar to keep rows clear of. */
	readonly hasButtons: boolean;
	private isClosed = false;
	private claims: BoundBlock[] = [];

	constructor(pane: SettingsPane, sessionUser: string, confirm: Confirm) {
		const drafts = new Map<string, BindingDraft>();
		const host = {
			confirm,
			closed: () => this.isClosed,
			lost: () => toast.error(__("{0} did not save", [__(pane.label)])),
		};
		const draftOf = (binding: SettingsBinding) => {
			const name = resolveName(binding, sessionUser);
			const identity = `${binding.doctype}/${name}`;
			if (!drafts.has(identity))
				drafts.set(
					identity,
					new BindingDraft(binding.doctype, name, binding.type === "Single", host)
				);
			return drafts.get(identity)!;
		};
		for (const block of pane.blocks) {
			if (block.binding) {
				const bound = bind(block, draftOf(block.binding));
				this.bound.set(block.key, bound);
				this.claims.push(bound);
			} else if (block.bindings && Object.keys(block.bindings).length) {
				this.components.set(block.key, this.bindComponent(block, draftOf));
			}
		}
		this.loaded = Promise.all([...drafts.values()].map((draft) => draft.loaded)).then(() => {});

		const buttons = this.claims.filter(({ block }) => block.save_mode === "button");
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
		this.failedCount = computed(
			() =>
				new Set(buttons.filter((bound) => marked(bound, "error")).map(({ block }) => block.key))
					.size
		);
		this.saving = computed(() => buttons.some((bound) => marked(bound, "saving")));
	}

	/** In `auto` mode it saves; a failed field is sent again only by its own block. */
	async commit(bound: BoundBlock) {
		const { draft } = bound;
		draft.clearReverted(bound.fieldnames.value);
		if (bound.block.save_mode !== "auto") return;
		const own = new Set(bound.fieldnames.value);
		const fieldnames = this.fieldnamesOf(draft, "auto").filter(
			(fieldname) =>
				(draft.dirty(fieldname) || draft.state.marks[fieldname] === "saving") &&
				(draft.state.marks[fieldname] !== "error" || own.has(fieldname))
		);
		await this.saveOrHold(draft, "auto", fieldnames);
	}

	/** The Save bar: each binding's `button` changes, in parallel, with nothing rolled back. */
	async saveButtons() {
		const drafts = new Set(this.claims.map(({ draft }) => draft));
		await Promise.all(
			[...drafts].map((draft) =>
				this.saveOrHold(
					draft,
					"button",
					this.fieldnamesOf(draft, "button").filter((fieldname) => draft.dirty(fieldname))
				)
			)
		);
	}

	discardButtons() {
		for (const { block, draft, fieldnames } of this.claims)
			if (block.save_mode === "button") draft.discard(fieldnames.value);
	}

	/** True while a change no save holds would be lost: a `button` edit or a failed autosave. */
	unsaved(): boolean {
		return this.claims.some(({ draft, fieldnames }) => draft.unsaved(fieldnames.value).length > 0);
	}

	/** A save still in flight finishes; if it then fails, a toast names the pane. */
	close() {
		this.isClosed = true;
	}

	/** A component's named bindings; each claims the declared fields its doctype has, else the unclaimed ones. */
	private bindComponent(block: SettingsBlock, draftOf: (binding: SettingsBinding) => BindingDraft) {
		const named = Object.entries(block.bindings!).map(([name, binding]) => {
			const draft = draftOf(binding);
			const claim: BoundBlock = {
				block,
				draft,
				layout: computed(() => []),
				fieldnames: computed(() =>
					block.fields?.length ? declaredFields(block.fields, draft) : this.unclaimedFields(draft)
				),
			};
			this.claims.push(claim);
			return [
				name,
				componentBinding(
					draft,
					() => claim.fieldnames.value,
					() => this.commit(claim)
				),
			] as const;
		});
		return Object.fromEntries(named);
	}

	/** The fields of the draft's doctype that no generated block draws and no component declares. */
	private unclaimedFields(draft: BindingDraft): string[] {
		const claimed = new Set(
			this.claims
				.filter((claim) => claim.draft === draft && (claim.block.binding || claim.block.fields?.length))
				.flatMap((claim) => claim.fieldnames.value)
		);
		return metaFieldnames(draft).filter((fieldname) => !claimed.has(fieldname));
	}

	/** An insert checks every block's required fields; a patch only those of the blocks in its mode that send a field. */
	private async saveOrHold(draft: BindingDraft, mode: SaveMode, fieldnames: string[]) {
		if (!fieldnames.length) return;
		const held = new Set<string>();
		const missing: ReturnType<typeof missingRequired> = [];
		for (const bound of this.claims) {
			if (bound.draft !== draft || !(draft.state.isNew || sends(bound, mode, fieldnames))) continue;
			const empty = missingRequired(bound.layout.value, draft.state.doc);
			if (!empty.length) continue;
			missing.push(...empty);
			for (const fieldname of draft.state.isNew ? fieldnames : bound.fieldnames.value)
				held.add(fieldname);
		}
		if (missing.length)
			draft.hold(
				fieldnames.filter((fieldname) => held.has(fieldname)),
				missing
			);
		const sent = fieldnames.filter((fieldname) => !held.has(fieldname));
		if (sent.length) return draft.save(sent);
	}

	private fieldnamesOf(draft: BindingDraft, mode: SaveMode): string[] {
		const fieldnames = this.claims
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

/** A component with several bindings lists their fields in one list; each binding claims its doctype's. */
function declaredFields(declared: string[], draft: BindingDraft): string[] {
	const present = new Set(metaFieldnames(draft));
	return declared.filter((fieldname) => present.has(fieldname));
}

function metaFieldnames(draft: BindingDraft): string[] {
	return (draft.state.meta?.fields ?? []).map((field) => field.fieldname);
}

function sends(bound: BoundBlock, mode: SaveMode, fieldnames: string[]): boolean {
	return (
		bound.block.save_mode === mode &&
		bound.fieldnames.value.some((fieldname) => fieldnames.includes(fieldname))
	);
}

/** A Single is named after its doctype; `session_user` names the person signed in. */
function resolveName(binding: SettingsBinding, sessionUser: string): string {
	return binding.type === "Single" ? binding.doctype : sessionUser;
}
