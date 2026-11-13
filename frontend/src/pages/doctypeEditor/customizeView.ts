// What Customize shows on the canvas and the panel: only what the site changed, and what it may not.
import type { ComputedRef } from "vue";
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import { appValue, siteSetters } from "./customizeRules";
import type { FlatEdit, WorkingState } from "./editorModel";
import type { EditorState } from "./editorSource";

export interface FieldMarks {
	/** The site added it. */
	custom: boolean;
	/** The properties the site changed, saved or staged. */
	changed: string[];
	hidden: boolean;
}

export class CustomizeView {
	constructor(
		readonly state: EditorState,
		private base: WorkingState,
		private working: ComputedRef<WorkingState>,
		private staged: () => readonly FlatEdit[],
	) {}

	marks(fieldname: string): FieldMarks {
		const field = this.field(fieldname);
		return {
			custom: !this.isStandard(fieldname),
			changed: this.isStandard(fieldname) ? this.changed(fieldname) : [],
			hidden: Boolean(field?.hidden),
		};
	}

	isStandard(fieldname: string): boolean {
		return Boolean(this.working.value.customize?.standard.includes(fieldname));
	}

	/** An app's custom field: standard, though not in the app's DocType. */
	fromApp(fieldname: string): boolean {
		return Boolean(this.isStandard(fieldname) && (this.field(fieldname) as { is_custom_field?: number })?.is_custom_field);
	}

	lock(fieldname: string, property: string): string | undefined {
		return this.state.locks?.[fieldname]?.[property];
	}

	/** The types Customize Form lets a standard field become; `null` when any type goes. */
	fieldtypes(fieldname: string): string[] | null {
		if (!this.isStandard(fieldname)) return null;
		return this.state.fieldtype_changes?.[fieldname] ?? [];
	}

	/** What a reset of `property` puts back: the app's value. */
	appValue(fieldname: string, property: string): unknown {
		const loaded = this.base.fields.find((field) => field.fieldname === fieldname);
		return loaded && this.base.customize ? appValue(this.base.customize, loaded, property) : undefined;
	}

	/** The field a site's custom field is drawn after; `null` at the start of the form. */
	anchor(fieldname: string): RawMetaField | null | undefined {
		if (this.isStandard(fieldname)) return undefined;
		const drawn = this.working.value.layout.flatMap((tab) =>
			tab.sections.flatMap((section) => section.columns.flatMap((column) => column.fields)),
		);
		const index = drawn.indexOf(fieldname);
		if (index === -1) return undefined;
		return index ? (this.field(drawn[index - 1]) ?? null) : null;
	}

	/** A standard field cannot go, so its remove hides it. */
	hidesOnRemove(fieldname: string): boolean {
		return this.isStandard(fieldname);
	}

	/** The saved setters' properties, then each staged change; a staged reset takes one away. */
	private changed(fieldname: string): string[] {
		const changed = new Set(
			siteSetters(this.state)
				.filter((setter) => setter.field_name === fieldname)
				.map((setter) => setter.property),
		);
		for (const edit of this.staged()) {
			if (edit.fieldname !== fieldname) continue;
			if (edit.act === "fields.set_field_property") changed.add(edit.property as string);
			if (edit.act === "fields.reset_field_property") changed.delete(edit.property as string);
		}
		return [...changed];
	}

	private field(fieldname: string): RawMetaField | undefined {
		return this.working.value.fields.find((field) => field.fieldname === fieldname);
	}
}
