// The `layouts.*` acts and the layout a `canvas.*` act lands on, as `DesignState.layout`,
// `add_layout` and `CustomizeState.reset_to_app` apply them on save.
import type { FormLayoutType } from "@/recordPage/formLayoutSource/types";
import { EditRefused, LayoutTreeEditor } from "./layoutTree";
import {
	emptyTabs,
	fallbackTabs,
	findLayout,
	forked,
	typeRefusal,
	type LayoutRef,
	type LayoutsHolder,
	type TypeLayouts,
	type WorkingLayout,
} from "./workingLayouts";

/** `ANCHORED_TYPES`: a site field on these renders at its anchor until the site forks the layout. */
const ANCHORED_TYPES: FormLayoutType[] = ["Details", "New Record"];

export interface AddLayout {
	type: FormLayoutType;
	id: string;
	title?: string | null;
	condition?: string | null;
	/** A copy of the type's default, or one empty tab. */
	start?: "copy" | "empty";
}

/** Edits the layouts of a state it owns. */
export class LayoutReplay {
	constructor(private state: LayoutsHolder) {}

	/** The layout an edit names; a missing default is made from the fallback, as the save makes it. */
	resolve(ref: LayoutRef | undefined, fork = true): WorkingLayout {
		const type = ref?.type as FormLayoutType;
		const of = this.typeLayouts(type);
		if (fork) this.touch(of);
		const found = findLayout(this.state, ref!);
		if (found) return found;
		if (ref!.id) throw new EditRefused("This {0} layout no longer exists.", [type]);
		const made = this.newLayout(fallbackTabs(this.state, type));
		if (!fork) made.source = of.empty?.source ?? "fallback";
		of.layouts.push(made);
		return made;
	}

	tree(ref: LayoutRef | undefined, fork = true): LayoutTreeEditor {
		return new LayoutTreeEditor(this.resolve(ref, fork).tabs);
	}

	/** `place_without_fork`: an unforked Details or New Record anchors a site field, and a fallback Details reorders a standard one. */
	placesWithoutFork(ref: LayoutRef | undefined, fieldname: string): boolean {
		const type = ref?.type as FormLayoutType;
		if (this.state.mode !== "Customize" || !ANCHORED_TYPES.includes(type) || forked(this.state, type)) return false;
		const byDefault = findLayout(this.state, { type });
		if (ref!.id && ref!.id !== byDefault?.id) return false;
		return this.isSiteCustom(fieldname) || (type === "Details" && !byDefault);
	}

	add({ type, id, title, condition, start }: AddLayout) {
		const of = this.typeLayouts(type);
		if (!id || of.layouts.some((layout) => layout.id === id)) {
			throw new EditRefused("A new layout needs an id of its own.");
		}
		if (!condition) this.refuseSecondDefault(type);
		this.touch(of);
		const tabs = start === "empty" ? emptyTabs() : structuredClone(this.defaultTabs(type));
		of.layouts.push({ ...this.newLayout(tabs), id, title: title || null, condition: condition || null });
	}

	rename({ layout, title }: { layout: LayoutRef; title?: string | null }) {
		this.resolve(layout).title = title || null;
	}

	setCondition({ layout, condition }: { layout: LayoutRef; condition?: string | null }) {
		const found = this.resolve(layout);
		if (!condition) this.refuseSecondDefault(layout.type, found);
		found.condition = condition || null;
	}

	delete({ layout }: { layout: LayoutRef }) {
		const found = this.resolve(layout);
		if (!found.condition) throw new EditRefused("The default {0} layout cannot be deleted.", [layout.type]);
		const { layouts } = this.typeLayouts(layout.type);
		layouts.splice(layouts.indexOf(found), 1);
	}

	resetToApp({ type }: { type: FormLayoutType }) {
		const of = this.typeLayouts(type);
		of.layouts = structuredClone(of.app);
		of.touched = false;
	}

	renameField(old: string, renamed: string) {
		for (const [of, layout] of this.everyLayout()) {
			const tree = new LayoutTreeEditor(layout.tabs);
			if (!tree.fieldnames().includes(old) && !layout.omitted.includes(old)) continue;
			tree.rename_field(old, renamed);
			layout.omitted = layout.omitted.map((each) => (each === old ? renamed : each));
			this.touch(of);
		}
		const fallback = this.state.layouts.Details?.empty?.tabs;
		if (fallback) new LayoutTreeEditor(fallback).rename_field(old, renamed);
	}

	deleteField(fieldname: string) {
		for (const [of, layout] of this.everyLayout()) {
			const tree = new LayoutTreeEditor(layout.tabs);
			if (!tree.fieldnames().includes(fieldname) && !layout.omitted.includes(fieldname)) continue;
			tree.unplace_field({ fieldname });
			layout.omitted = layout.omitted.filter((each) => each !== fieldname);
			this.touch(of);
		}
		const fallback = this.state.layouts.Details?.empty?.tabs;
		if (fallback) new LayoutTreeEditor(fallback).unplace_field({ fieldname });
	}

	private isSiteCustom(fieldname: string): boolean {
		const field = this.state.fields.find((one) => one.fieldname === fieldname) as
			| { is_custom_field?: 0 | 1; is_system_generated?: 0 | 1 }
			| undefined;
		if (!this.state.saved.includes(fieldname)) return true;
		return Boolean(field?.is_custom_field && !field.is_system_generated);
	}

	private typeLayouts(type: FormLayoutType): TypeLayouts {
		const refusal = typeRefusal(this.state, type);
		if (refusal) throw refusal;
		return this.state.layouts[type]!;
	}

	/** `default_tabs`: the default's tree, else what the fallback makes. */
	private defaultTabs(type: FormLayoutType) {
		return findLayout(this.state, { type })?.tabs ?? fallbackTabs(this.state, type);
	}

	/** Customize forks a type it touches: every layout of it saves as a site row. */
	private touch(of: TypeLayouts) {
		of.touched = true;
		if (this.state.mode === "Customize") for (const layout of of.layouts) layout.source = "site";
	}

	private newLayout(tabs: WorkingLayout["tabs"]): WorkingLayout {
		const source = this.state.mode === "Design" && this.state.standard ? "app" : "site";
		return { title: null, condition: null, source, tabs, omitted: [] };
	}

	private refuseSecondDefault(type: FormLayoutType, except?: WorkingLayout) {
		const other = this.typeLayouts(type).layouts.find((layout) => !layout.condition && layout !== except);
		if (other) {
			throw new EditRefused("Only one {0} layout can have no condition. Add a condition to the others.", [type]);
		}
	}

	private *everyLayout(): Generator<[TypeLayouts, WorkingLayout]> {
		for (const of of Object.values(this.state.layouts)) {
			for (const layout of of!.layouts) yield [of!, layout];
		}
	}
}
