// The view switcher's menu as frappe-ui `Dropdown` groups: every view of the doctype by layer,
// then the open view's acts. Pure: the host says who is asking and what a row runs.
import { Badge, type DropdownOptions } from "frappe-ui";
import { h, type FunctionalComponent } from "vue";
import { withAct } from "@/acts/menuAct";
import { __ } from "@/i18n";
import Icon from "@/icons/Icon.vue";
import type { ListedView } from "@/list/listedViews";
import { actsOn, siteDefaultBlocked, type ViewAct } from "./viewRules";

export type ViewRequestKind = "rename" | "save_as_new" | "delete" | "restore" | "publish";

/** A dialog the menu opens; the view is the one it acts on. */
export type ViewRequest = { kind: ViewRequestKind; view?: ListedView };

export interface ViewType {
	name: string;
	label: string;
	icon: string | null;
}

export interface ViewMenuHost {
	/** The doctype's views from `list_views`; null while the first read runs. */
	views: ListedView[] | null;
	/** False while the sidebar lists the views: the menu then holds only the open view's acts. */
	listsViews?: boolean;
	/** The open view's key. */
	current: string;
	/** View types not built yet; they list as "Soon". */
	unbuilt: ViewType[];
	/** Every View Type, for a row's icon. */
	types: ViewType[];
	admin: boolean;
	/** The plain view has filters or a sort on it. */
	plainModified: boolean;
	/** True while the page draws the act, so a script that hides it takes its row away. */
	drawn: (act: string) => boolean;
	run: (act: string, value?: unknown) => void;
	ask: (request: ViewRequest) => void;
}

const LAYERS: { layer: ListedView["layer"]; label: () => string }[] = [
	{ layer: null, label: () => __("Types") },
	{ layer: "own", label: () => __("My views") },
	{ layer: "site", label: () => __("Site views") },
	{ layer: "app", label: () => __("App views") },
];

export type Row = Record<string, any>;
export type Group = { group: string; hideLabel?: boolean; options: Row[] };

/** The menu: Save as new, the views by layer (unless the sidebar lists them), then the open view's acts. */
export function viewMenu(host: ViewMenuHost): DropdownOptions {
	if (!host.views) return [{ label: __("Loading views…"), disabled: true }];
	const open = host.views.find((view) => view.key === host.current);
	// With no open view there are no acts to show, so the list stays.
	const views = host.listsViews === false && open ? [] : viewGroups(host);
	return [...saveAsNew(host, open), ...views, ...(open ? actGroups(host, open) : [])]
		.filter((group) => group.options.length) as DropdownOptions;
}

/** One layer of the doctype's views; Types also holds the view types not built yet. */
export interface ViewLayerGroup {
	layer: ListedView["layer"];
	label: string;
	views: ListedView[];
	soon: ViewType[];
}

/** The views by layer, empty layers kept: the menu and the sidebar group them alike. */
export function viewLayers(views: ListedView[], unbuilt: ViewType[]): ViewLayerGroup[] {
	return LAYERS.map(({ layer, label }) => ({
		layer,
		label: label(),
		views: views.filter((view) => view.layer === layer),
		soon: layer === null ? unbuilt : [],
	}));
}

function viewGroups(host: ViewMenuHost): Group[] {
	return viewLayers(host.views!, host.unbuilt).map((group) => ({
		group: group.label,
		hideLabel: group.layer === null,
		options: [
			...group.views.map((view) => viewRow(host, view)),
			...group.soon.map((type) => soonRow(host, type)),
		],
	}));
}

function viewRow(host: ViewMenuHost, view: ListedView): Row {
	const row = {
		label: view.label,
		icon: iconOf(host, view.type),
		selected: view.key === host.current,
		onClick: () => host.run("open_view", { key: view.key }),
	};
	return withSuffix(withAct(row, "list.open_view"), view.default ? DEFAULT_MARK : undefined);
}

function soonRow(host: ViewMenuHost, type: ViewType): Row {
	const key = type.name.toLowerCase();
	const row = {
		label: type.label,
		icon: iconFor(type.icon),
		selected: key === host.current,
		onClick: () => host.run("open_view", { key }),
	};
	return withSuffix(withAct(row, "list.open_view"), SOON_BADGE);
}

// A saved view's changes are the save bar's, not this row's.
function saveAsNew(host: ViewMenuHost, open?: ListedView): Group[] {
	if (!host.plainModified || open?.layer !== null || !host.drawn("save_view_as")) return [];
	const row = withAct(
		{
			label: __("Save as new view…"),
			icon: "lucide-copy-plus",
			onClick: () => host.ask({ kind: "save_as_new", view: open }),
		},
		"list.save_view_as"
	);
	return [{ group: __("Changes"), hideLabel: true, options: [row] }];
}

/** The acts the person may run on one view, as the menu's groups. */
export function actGroups(host: ViewMenuHost, view: ListedView): Group[] {
	const acts = actsOn(view, host.admin);
	const pick = (names: ViewAct[]) =>
		names
			.filter((name) => acts.includes(name))
			.map((name) => actRow(host, view, name))
			.filter((row): row is Row => row !== null);
	return [
		{ group: __("View"), hideLabel: true, options: pick(["rename", "publish", "delete", "restore"]) },
		{
			group: __("Default"),
			hideLabel: true,
			options: pick(["set_mine", "clear_mine", "set_site", "clear_site"]),
		},
	].filter((group) => group.options.length);
}

function actRow(host: ViewMenuHost, view: ListedView, name: ViewAct): Row | null {
	const confirmed = (kind: ViewRequestKind) => () => host.ask({ kind, view });
	const key = view.key;
	const rows: Record<ViewAct, [string, string, string, () => void, Row?]> = {
		rename: [__("Rename"), "lucide-pencil", "rename_view", confirmed("rename")],
		publish: [__("Publish to site"), "lucide-globe", "publish_view", confirmed("publish")],
		delete: [__("Delete"), "lucide-trash-2", "delete_view", confirmed("delete"), { theme: "red" }],
		restore: [__("Restore the app's view"), "lucide-rotate-ccw", "delete_view", confirmed("restore")],
		set_mine: [__("Set as my default"), "lucide-house", "set_default_view", () => host.run("set_default_view", { key, scope: "user" })],
		clear_mine: [__("Remove my default"), "lucide-house", "clear_default_view", () => host.run("clear_default_view", { scope: "user" })],
		set_site: [__("Set as default for everyone"), "lucide-users", "set_default_view", () => host.run("set_default_view", { key, scope: "site" }), siteDefaultMark(view)],
		clear_site: [__("Remove default for everyone"), "lucide-users", "clear_default_view", () => host.run("clear_default_view", { scope: "site" })],
	};
	const [label, icon, act, onClick, extra] = rows[name];
	return host.drawn(act) ? withAct({ label, icon, onClick, ...extra }, `list.${act}`) : null;
}

function siteDefaultMark(view: ListedView): Row {
	return siteDefaultBlocked(view) ? { disabled: true, description: __("Publish this view first") } : {};
}

function iconOf(host: ViewMenuHost, type: string) {
	return iconFor(host.types.find((one) => one.name === type)?.icon);
}

// A type's icon is a bare sprite name that arrives with boot: the menu takes a component that draws it.
const icons = new Map<string, FunctionalComponent>();
function iconFor(name?: string | null): FunctionalComponent | undefined {
	if (!name) return undefined;
	if (!icons.has(name)) icons.set(name, (_props, { attrs }) => h(Icon, { name, class: attrs.class }));
	return icons.get(name);
}

const DEFAULT_MARK = () => h("span", { class: "ml-2 text-sm leading-none text-ink-gray-6" }, __("Default"));
const SOON_BADGE = () => h("span", { class: "ml-2 flex" }, h(Badge, { label: __("Soon"), theme: "gray", size: "sm" }));

// `withAct` puts its mark on the label slot; the suffix slot sits beside it.
function withSuffix<T extends { slots: object }>(row: T, suffix?: () => unknown): T {
	return suffix ? { ...row, slots: { ...row.slots, suffix } } : row;
}
