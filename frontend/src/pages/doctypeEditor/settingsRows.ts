// The Settings tab's catalogue: its sections, and each row with the property it sets. The tab
// draws from it, and Mod+J finds a setting in it.
import type { SettingsState } from "./settingsModel";

export type SettingsSection = "naming" | "form" | "list" | "permissions";
export type DoctypeKind = "regular" | "submittable" | "tree" | "child" | "single";
export type RowControl = "naming" | "kind" | "switch" | "number" | "field" | "fields" | "sort" | "view" | "permissions";

export interface SettingRow {
	key: string;
	section: SettingsSection;
	/** The small heading the row sits under; "" for none. */
	group: string;
	label: string;
	help: string;
	control: RowControl;
	/** The DocType properties it sets: the first is its lock and reset; a save error on any marks the row. */
	props: string[];
	/** The field types a `field` or `fields` control offers. */
	fieldtypes?: string[];
	keywords?: string;
	/** The kinds of DocType that show it; all when absent. */
	kinds?: DoctypeKind[];
	/** Only while the DocType is not yet saved. */
	pending?: boolean;
}

export const SECTIONS: { key: SettingsSection; label: string; icon: string }[] = [
	{ key: "naming", label: "Naming", icon: "lucide-hash" },
	{ key: "form", label: "Form", icon: "lucide-file-text" },
	{ key: "list", label: "List and search", icon: "lucide-list" },
	{ key: "permissions", label: "Permissions", icon: "lucide-shield" },
];

export const KINDS: { value: DoctypeKind; label: string; description: string }[] = [
	{ value: "regular", label: "Regular", description: "Many records, with a list to find them in." },
	{ value: "child", label: "Child table", description: "Rows inside another DocType's table. No list of its own." },
	{ value: "single", label: "Single", description: "One record only, like a settings page." },
	{ value: "submittable", label: "Submittable", description: "Records are drafted, then submitted and locked." },
	{ value: "tree", label: "Tree", description: "Records nest under each other, like groups and their members." },
];

const MANY: DoctypeKind[] = ["regular", "submittable", "tree"];
const NOT_CHILD: DoctypeKind[] = [...MANY, "single"];
const NOT_SINGLE: DoctypeKind[] = [...MANY, "child"];
const TITLE_TYPES = ["Data", "Small Text", "Link", "Select", "Dynamic Link", "Read Only"];
const SEARCH_TYPES = [...TITLE_TYPES, "Int", "Float", "Currency", "Date", "Phone"];

const flag = (section: SettingsSection, group: string, prop: string, label: string, help: string, kinds?: DoctypeKind[]): SettingRow => ({
	key: prop,
	section,
	group,
	label,
	help,
	control: "switch",
	props: [prop],
	kinds,
});

export const SETTING_ROWS: SettingRow[] = [
	{
		key: "naming",
		section: "naming",
		group: "",
		label: "Naming rule",
		help: "How each new record gets its ID.",
		control: "naming",
		props: ["autoname", "naming_rule", "naming_series"],
		keywords: "autoname naming series pattern format expression random hash autoincrement number prompt field",
		kinds: MANY,
	},
	{ ...flag("naming", "", "allow_rename", "Allow rename", "People who can write a record can rename it.", MANY), keywords: "name" },
	{
		key: "kind",
		section: "form",
		group: "Record",
		label: "Kind",
		help: "Set when the DocType is made; it cannot change once saved.",
		control: "kind",
		props: ["istable", "issingle", "is_submittable", "is_tree"],
		keywords: "child table single submittable tree type",
		pending: true,
	},
	{
		key: "title_field",
		section: "form",
		group: "Record",
		label: "Title field",
		help: "Lists, links and headings show it instead of the ID.",
		control: "field",
		props: ["title_field"],
		fieldtypes: TITLE_TYPES,
		kinds: MANY,
	},
	{
		key: "image_field",
		section: "form",
		group: "Record",
		label: "Image field",
		help: "The picture lists, links and the heading show.",
		control: "field",
		props: ["image_field"],
		fieldtypes: ["Attach Image"],
		kinds: MANY,
	},
	flag("form", "Record", "queue_in_background", "Save in the background", "A save runs as a background job.", NOT_CHILD),
	flag("form", "Creating", "quick_entry", "Quick entry", "A new record opens in a dialog of the required fields.", MANY),
	flag("form", "Creating", "allow_copy", "Hide copy", "A record's menu has no Duplicate.", MANY),
	flag("form", "Creating", "allow_auto_repeat", "Auto repeat", "A record can repeat on a schedule.", MANY),
	flag("form", "Tracking", "track_changes", "Track changes", "Keeps each save's changes in the record's activity."),
	flag("form", "Tracking", "track_views", "Track views", "Notes who opened each record.", NOT_CHILD),
	flag("form", "Tracking", "track_seen", "Track seen", "Marks a record seen once each person opens it.", NOT_CHILD),
	{
		...flag("form", "Attachments", "max_attachments", "Max attachments", "Files one record can hold; 0 is no limit.", NOT_CHILD),
		control: "number",
	},
	flag("form", "Attachments", "make_attachments_public", "Make attachments public", "New attachments are public files by default.", NOT_CHILD),
	flag("form", "Attachments", "force_private_attachments", "Keep attachments private", "Every attachment is a private file.", NOT_CHILD),
	flag("form", "Attachments", "protect_attached_files", "Protect attached files", "A submitted record's files cannot be removed.", NOT_CHILD),
	flag("form", "Rows", "editable_grid", "Editable grid", "Rows are edited in the parent's table, not a dialog.", ["child"]),
	{
		key: "default_view",
		section: "list",
		group: "List",
		label: "Default view",
		help: "The view the DocType opens in.",
		control: "view",
		props: ["default_view"],
		kinds: MANY,
	},
	{
		key: "sort_field",
		section: "list",
		group: "List",
		label: "Default sort",
		help: "The order a list opens in.",
		control: "sort",
		props: ["sort_field", "sort_order"],
		fieldtypes: ["Date", "Datetime", "Data", "Link", "Select", "Int", "Float", "Currency"],
		keywords: "order",
		kinds: MANY,
	},
	flag("list", "List", "is_calendar_and_gantt", "Calendar and Gantt", "Offers the calendar and Gantt views.", MANY),
	{
		key: "search_fields",
		section: "list",
		group: "Search",
		label: "Search by",
		help: "A Link field's search matches these fields as well as the ID.",
		control: "fields",
		props: ["search_fields"],
		fieldtypes: SEARCH_TYPES,
		kinds: MANY,
	},
	flag("list", "Search", "show_name_in_global_search", "In global search", "The search bar finds records by their ID.", MANY),
	flag("list", "Links", "show_title_field_in_link", "Show the title in links", "A Link field shows the title next to the ID.", MANY),
	flag("list", "Links", "show_image_in_link", "Show the image in links", "A Link field's search shows each record's image.", MANY),
	flag("list", "Import", "allow_import", "Allow import", "Records can come in from a spreadsheet.", MANY),
	flag("list", "Import", "allow_bulk_edit", "Allow bulk edit", "Many rows can be edited at once.", NOT_SINGLE),
	{
		key: "permissions",
		section: "permissions",
		group: "",
		label: "Roles and rights",
		help: "Which roles read, write, create and delete records.",
		control: "permissions",
		props: ["permissions"],
		keywords: "permission rules role roles rights access level custom docperm",
		kinds: NOT_CHILD,
	},
];

export function kindOf(properties: Record<string, unknown>): DoctypeKind {
	if (Number(properties.issingle)) return "single";
	if (Number(properties.istable)) return "child";
	if (Number(properties.is_tree)) return "tree";
	return Number(properties.is_submittable) ? "submittable" : "regular";
}

/** The kind's four flags, as `settings.set_doctype_property` sets them. */
export function kindProperties(kind: DoctypeKind): Record<string, 0 | 1> {
	return {
		istable: kind === "child" ? 1 : 0,
		issingle: kind === "single" ? 1 : 0,
		is_submittable: kind === "submittable" ? 1 : 0,
		is_tree: kind === "tree" ? 1 : 0,
	};
}

/** The rows this DocType shows. */
export function settingRows(settings: SettingsState): SettingRow[] {
	const kind = kindOf(settings.properties);
	return SETTING_ROWS.filter((row) => (!row.kinds || row.kinds.includes(kind)) && (!row.pending || settings.pending));
}

/** The sections with at least one row: a child table has no Naming or Permissions, a Single no Naming. */
export function settingSections(settings: SettingsState) {
	const rows = settingRows(settings);
	return SECTIONS.filter((section) => rows.some((row) => row.section === section.key));
}

/** The row a save error's property marks. */
export function rowOf(settings: SettingsState, property: string): SettingRow | undefined {
	return settingRows(settings).find((row) => row.props.includes(property));
}
