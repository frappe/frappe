// The Settings tab's working state: DocType properties, the naming series and permission rows.
// Each act applies as `frappe/desk/doctype_editor/settings_edits.py` (and, in Customize,
// `customize_edits.py`) applies it on save.
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import type { EditorState } from "./editorSource";
import { EditRefused } from "./layoutTree";

/** `frappe.permissions.std_rights`. */
export const RIGHTS = [
	"select",
	"read",
	"write",
	"create",
	"delete",
	"submit",
	"cancel",
	"amend",
	"print",
	"email",
	"report",
	"import",
	"export",
	"share",
] as const;
export type Right = (typeof RIGHTS)[number];

/** Ticking a right ticks these; unticking one of them unticks the rights that need it. */
const PREREQUISITES: Partial<Record<Right, Right[]>> = {
	cancel: ["submit"],
	submit: ["write"],
	amend: ["write", "create"],
	import: ["create"],
};
/** Set when the DocType is created; a saved one refuses them. */
export const KIND_PROPERTIES = ["istable", "issingle", "is_submittable", "is_tree"];
const AUTOINCREMENT = "autoincrement";

export type PermissionRow = { role: string; permlevel: number; if_owner: 0 | 1 } & Record<Right, 0 | 1>;
export type PermissionKey = Pick<PermissionRow, "role" | "permlevel" | "if_owner">;

export interface SettingsState {
	properties: Record<string, unknown>;
	/** The properties this mode sets, the others show locked; `null` before the first save: the save checks. */
	settable: string[] | null;
	permissions: PermissionRow[];
	/** Not yet saved: its kind may still change. */
	pending: boolean;
	/** Readable records, `null` when unknown: "Number in order" waits for none. */
	records: number | null;
	/** The naming rule the database has: switching to or from "Number in order" checks it. */
	savedAutoname: string | undefined;
	/** Customize: what the app ships, for the resets; `null` in Design. */
	app: { properties: Record<string, unknown>; permissions: PermissionRow[] } | null;
	/** Customize: the rows are the site's own (Custom DocPerm), replacing the app's. */
	sitePermissions: boolean;
	/** Why the permission acts are refused; "" when they are not. */
	permissionsRefusal: string;
}

/** The fields part of the working state a naming series edit adds to. */
export interface SettingsHost {
	settings: SettingsState;
	fields: RawMetaField[];
	addField(edit: { act: string; label: string; fieldname: string; fieldtype: string }): void;
}

/** This mode sets the property; before the first save every property is, and the save checks. */
export function settable(settings: Pick<SettingsState, "settable">, property: string): boolean {
	return !settings.settable || settings.settable.includes(property);
}

export function settingsBase(state: EditorState): SettingsState {
	const { definition } = state;
	const { fields: _fields, permissions, ...properties } = definition;
	const customize = state.mode === "Customize";
	return {
		properties,
		settable: state.settable_properties ?? null,
		permissions: (permissions ?? []).map(permissionRow),
		pending: Boolean(state.pending),
		records: state.record_count,
		savedAutoname: definition.autoname,
		app: customize ? { properties: appProperties(state), permissions: (state.app_permissions ?? []).map(permissionRow) } : null,
		sitePermissions: Boolean(state.site_permissions),
		permissionsRefusal: state.permissions_refusal ?? "",
	};
}

/** The right with its prerequisites when ticked, or with its dependents when unticked. */
export function closure(right: Right, ticked: boolean): Set<Right> {
	const found = new Set<Right>();
	const todo: Right[] = [right];
	while (todo.length) {
		const each = todo.pop()!;
		found.add(each);
		if (ticked) todo.push(...(PREREQUISITES[each] ?? []).filter((need) => !found.has(need)));
		else {
			const dependents = Object.entries(PREREQUISITES).filter(([, needs]) => needs.includes(each));
			todo.push(...dependents.map(([dependent]) => dependent as Right).filter((one) => !found.has(one)));
		}
	}
	return found;
}

export function sameKey(row: PermissionKey, key: PermissionKey): boolean {
	return row.role === key.role && row.permlevel === Number(key.permlevel ?? 0) && row.if_owner === (key.if_owner ? 1 : 0);
}

/** Applies `settings.*` acts to a state it owns. */
export class SettingsReplay {
	constructor(private host: SettingsHost) {}

	private get state(): SettingsState {
		return this.host.settings;
	}

	apply(edit: { act: string; [key: string]: unknown }) {
		const handler = SETTINGS_ACTS[edit.act];
		if (!handler) throw new EditRefused("{0} is not a Settings edit.", [edit.act]);
		handler(this, edit as never);
	}

	setDoctypeProperty({ property, value }: { property: string; value: unknown }) {
		this.refuseProperty(property);
		if (property === "autoname") this.refuseAutoincrement(value as string);
		this.state.properties[property] = value;
	}

	resetDoctypeProperty({ property }: { property: string }) {
		const app = this.customizeOnly();
		this.refuseProperty(property);
		this.state.properties[property] = app.properties[property];
	}

	setNamingSeries({ options, default: preferred }: { options?: string[]; default?: string }) {
		const list = (options ?? []).map((option) => option.trim());
		if (!list.length || list.some((option) => !option) || new Set(list).size < list.length) {
			throw new EditRefused("Give each naming series once, and none empty.");
		}
		const chosen = preferred || list[0];
		if (!list.includes(chosen)) throw new EditRefused("The default series must be one of the list.");
		const field = this.seriesField();
		Object.assign(field, { options: list.join("\n"), default: chosen });
	}

	addPermission(key: PermissionKey) {
		const rows = this.ownRows();
		if (rows.some((row) => sameKey(row, key))) {
			throw new EditRefused("{0} already has a row at level {1}.", [key.role, String(key.permlevel ?? 0)]);
		}
		const rights = Object.fromEntries(RIGHTS.map((right) => [right, right === "read" ? 1 : 0]));
		rows.push(permissionRow({ ...rights, ...key }));
	}

	removePermission(key: PermissionKey) {
		const rows = this.ownRows();
		rows.splice(rows.indexOf(this.permission(key)), 1);
	}

	setPermission(edit: PermissionKey & { right: Right; value: unknown }) {
		if (!RIGHTS.includes(edit.right)) throw new EditRefused("{0} is not a permission.", [edit.right]);
		const row = this.permission(edit, this.ownRows());
		for (const right of closure(edit.right, Boolean(edit.value))) row[right] = edit.value ? 1 : 0;
	}

	resetPermissions() {
		this.refusePermissions();
		const app = this.customizeOnly();
		this.state.permissions = structuredClone(app.permissions);
		this.state.sitePermissions = false;
	}

	private refuseProperty(property: string) {
		if (KIND_PROPERTIES.includes(property)) {
			if (this.state.pending) return;
			throw new EditRefused("{0} is set when the DocType is created.", [property]);
		}
		if (!settable(this.state, property)) {
			throw new EditRefused("{0} is not a DocType setting the editor sets.", [property]);
		}
	}

	private refuseAutoincrement(value: string) {
		const saved = this.state.savedAutoname;
		if (!(value === AUTOINCREMENT || saved === AUTOINCREMENT) || value === saved || this.state.pending) return;
		if (this.state.app) throw new EditRefused("Customize cannot switch to or from Number in order.");
		// An unknown count leaves the refusal to the save.
		if (this.state.records && !this.state.properties.issingle) {
			throw new EditRefused("Number in order can only be switched to or from while there are no records.");
		}
	}

	private seriesField(): RawMetaField {
		const field = this.host.fields.find((one) => one.fieldname === "naming_series");
		if (field) return field;
		if (this.state.app) throw new EditRefused("This DocType has no naming_series field.");
		this.host.addField({ act: "fields.add_field", label: "Series", fieldname: "naming_series", fieldtype: "Select" });
		const added = this.host.fields.find((one) => one.fieldname === "naming_series")!;
		added.reqd = 1;
		return added;
	}

	private refusePermissions() {
		if (this.state.permissionsRefusal) throw new EditRefused(this.state.permissionsRefusal);
	}

	/** In Customize, the first permission edit makes the rows the site's own. */
	private ownRows(): PermissionRow[] {
		this.refusePermissions();
		if (this.state.app) this.state.sitePermissions = true;
		return this.state.permissions;
	}

	private permission(key: PermissionKey, rows = this.state.permissions): PermissionRow {
		const row = rows.find((one) => sameKey(one, key));
		if (!row) throw new EditRefused("{0} has no row at level {1}.", [key.role, String(key.permlevel ?? 0)]);
		return row;
	}

	private customizeOnly() {
		if (!this.state.app) throw new EditRefused("Only Customize resets a setting to the app's value.");
		return this.state.app;
	}
}

const SETTINGS_ACTS: Record<string, (replay: SettingsReplay, edit: never) => void> = {
	"settings.set_doctype_property": (replay, edit) => replay.setDoctypeProperty(edit),
	"settings.reset_doctype_property": (replay, edit) => replay.resetDoctypeProperty(edit),
	"settings.set_naming_series": (replay, edit) => replay.setNamingSeries(edit),
	"settings.add_permission": (replay, edit) => replay.addPermission(edit),
	"settings.remove_permission": (replay, edit) => replay.removePermission(edit),
	"settings.set_permission": (replay, edit) => replay.setPermission(edit),
	"settings.reset_permissions": (replay) => replay.resetPermissions(),
};

/** The app's value of each DocType property the site set: the meta's value, except where a site setter overrides it. */
function appProperties(state: EditorState): Record<string, unknown> {
	const { fields: _fields, permissions: _permissions, ...properties } = state.definition;
	const siteSetters = (state.property_setters ?? []).filter(
		(setter) => setter.doctype_or_field === "DocType" && !setter.is_system_generated,
	);
	return { ...properties, ...Object.fromEntries(siteSetters.map((setter) => [setter.property, setter.app_value])) };
}

function permissionRow(row: Record<string, unknown>): PermissionRow {
	const rights = Object.fromEntries(RIGHTS.map((right) => [right, row[right] ? 1 : 0]));
	return { ...rights, role: row.role as string, permlevel: Number(row.permlevel ?? 0), if_owner: row.if_owner ? 1 : 0 } as PermissionRow;
}
