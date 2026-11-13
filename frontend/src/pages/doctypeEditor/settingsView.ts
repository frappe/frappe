// What the Settings tab's rows read and do: a setting's value, its Customize lock and changed dot,
// and the acts that change it. Each change goes through `acts.perform`, so it joins the header's
// Save and the one undo stack.
import type { InjectionKey, Ref } from "vue";
import type { RouteLocationRaw } from "vue-router";
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import { acts } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import type { DesignCanvas } from "./designCanvas";
import { namingProperties } from "./namingRules";
import type { SettingsState } from "./settingsModel";
import { kindOf, type SettingRow, type SettingsSection } from "./settingsRows";

/** The tab's open section, and the row Mod+J last found (flashed once). */
export interface SettingsPlace {
	section: SettingsSection | "";
	found: { key: string; at: number } | null;
}

export const SettingsViewKey: InjectionKey<SettingsView> = Symbol("SettingsView");

/** A value as Customize Form compares it: unset, 0 and "" are the same. */
export const normal = (value: unknown) =>
	value === undefined || value === null || value === 0 || value === "0" ? "" : String(value);

export class SettingsView {
	constructor(
		private canvas: DesignCanvas,
		readonly place: Ref<SettingsPlace>,
		/** Where Customize opens; null when this DocType has no Customize. */
		readonly customizeRoute: () => RouteLocationRaw | null,
	) {}

	get settings(): SettingsState {
		return this.canvas.working.value.settings;
	}

	get fields(): RawMetaField[] {
		return this.canvas.working.value.fields;
	}

	get doctype() {
		return this.canvas.state.doctype;
	}

	get mode() {
		return this.canvas.state.mode;
	}

	/** Design: the site has its own permission rules (Custom DocPerm), which Customize edits. */
	get siteOverridesPermissions() {
		return !this.customize && Boolean(this.canvas.state.site_permissions);
	}

	get customize() {
		return this.settings.app !== null;
	}

	get kind() {
		return kindOf(this.settings.properties);
	}

	/** The app the DocType ships in, for Customize's wording. */
	get app() {
		return this.canvas.state.app_title || __("the app");
	}

	value(prop: string): unknown {
		return this.settings.properties[prop];
	}

	/** Why this mode cannot change the row's setting; "" when it can. */
	lock(row: SettingRow): string {
		const { settable } = this.settings;
		if (row.control === "permissions" || row.pending || !settable) return "";
		if (settable.includes(row.props[0])) return "";
		return this.customize
			? __("Only {0}'s DocType sets this. Customize cannot change it.", [this.app])
			: __("The editor does not set this.");
	}

	/** Customize: the site's value differs from the app's. */
	changed(row: SettingRow): boolean {
		const app = this.settings.app;
		if (!app || row.control === "permissions") return false;
		return row.props.some((prop) => prop in app.properties && normal(this.value(prop)) !== normal(app.properties[prop]));
	}

	appValue(prop: string): unknown {
		return this.settings.app?.properties[prop];
	}

	label(fieldname: string): string {
		const field = this.fields.find((one) => one.fieldname === fieldname);
		return field?.label ? __(field.label, [], this.doctype) : fieldname;
	}

	/** The working fields of these types, as picker options. */
	fieldOptions(fieldtypes: string[]) {
		return this.fields
			.filter((field) => fieldtypes.includes(field.fieldtype))
			.map((field) => ({ label: this.label(field.fieldname), value: field.fieldname }));
	}

	/** The save's errors at the row. */
	errors(row: SettingRow): string[] {
		return row.props.flatMap((prop) => this.canvas.errorsAt("setting", prop));
	}

	/** Sets each changed property, as one undo step. */
	set(values: Record<string, unknown>) {
		const changes = Object.entries(values)
			.filter(([prop, value]) => normal(this.value(prop)) !== normal(value))
			.map(([property, value]) => ({ property, value }));
		if (changes.length) void acts.perform("settings.set_doctype_property", changes);
	}

	reset(row: SettingRow) {
		const app = this.settings.app;
		const props = row.props.filter((prop) => app && normal(this.value(prop)) !== normal(app.properties[prop]));
		if (props.length) void acts.perform("settings.reset_doctype_property", props.map((property) => ({ property })));
	}

	/** Sets the naming rule's two properties, and a new series list with them, as one undo step. */
	setNaming(autoname: string, series?: string[]) {
		const changes: Record<string, unknown>[] = Object.entries(namingProperties(autoname))
			.filter(([prop, value]) => normal(this.value(prop)) !== normal(value))
			.map(([property, value]) => ({ property, value }));
		if (series) changes.push({ act: "settings.set_naming_series", options: series });
		if (changes.length) void acts.perform("settings.set_doctype_property", changes);
	}

	setSeries(options: string[], preferred: string) {
		void acts.perform("settings.set_naming_series", { options, default: preferred });
	}

	/** A permission act: add, remove, set or reset rules. */
	permission(act: "add_permission" | "remove_permission" | "set_permission" | "reset_permissions", keys = {}) {
		void acts.perform(`settings.${act}`, keys);
	}
}
