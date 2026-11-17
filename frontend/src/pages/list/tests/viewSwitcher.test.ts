// The view switcher's menu: its groups and their order, the Default label, which acts each person
// sees on each kind of view, and what a pick opens.
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Router } from "vue-router";
import type { ListedView } from "@/list/listedViews";
import { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { registerShell } from "@/router/routeFor";
import { clearSkip, consumeSkip } from "@/router/skipDefault";
import { openView } from "../openView";
import { viewLayers, viewMenu, type ViewMenuHost, type ViewRequest } from "../viewSwitcher/viewMenu";
import { actsOn, isSiteAdmin } from "../viewSwitcher/viewRules";

type Row = Record<string, any>;
type Group = { group: string; hideLabel?: boolean; options: Row[] };

const TYPES = [
	{ name: "List", label: "List", icon: "list" },
	{ name: "Cards", label: "Cards", icon: "layout-grid" },
];
const SOON = [
	{ name: "Kanban", label: "Kanban", icon: "kanban" },
	{ name: "Calendar", label: "Calendar", icon: "calendar" },
];

const view = (key: string, layer: ListedView["layer"], extra: Partial<ListedView> = {}): ListedView => ({
	key,
	label: key[0].toUpperCase() + key.slice(1),
	type: "List",
	layer,
	...extra,
});

const VIEWS: ListedView[] = [
	view("list", null, { default: true }),
	view("cards", null, { type: "Cards" }),
	view("app-open", "app"),
	view("mine", "own"),
	view("shared", "site"),
	view("mine-too", "own"),
];

function host(over: Partial<ViewMenuHost> = {}) {
	const run = vi.fn();
	const ask = vi.fn<(request: ViewRequest) => void>();
	const menu: ViewMenuHost = {
		views: VIEWS,
		current: "mine",
		unbuilt: SOON,
		types: TYPES,
		admin: false,
		plainModified: false,
		drawn: () => true,
		run,
		ask,
		...over,
	};
	return { menu, run, ask };
}

const groups = (over: Partial<ViewMenuHost> = {}) => viewMenu(host(over).menu) as unknown as Group[];
const labels = (list: Group[]) => list.flatMap((group) => group.options.map((row) => row.label));
// The rows of the acts below the views: everything after the last view group.
const actLabels = (over: Partial<ViewMenuHost> = {}) =>
	labels(groups(over).filter((group) => ["View", "Default"].includes(group.group)));
const row = (list: Group[], label: string) => list.flatMap((group) => group.options).find((one) => one.label === label)!;
const mark = (one: Row) => one.slots.label({ item: one }).props;

describe("the menu's groups", () => {
	it("lists Types, My views, Site views and App views in that order, then the open view's acts", () => {
		expect(groups({ current: "mine" }).map((group) => group.group)).toEqual([
			"Types",
			"My views",
			"Site views",
			"App views",
			"View",
			"Default",
		]);
	});

	it("leaves the Types heading out and keeps the others", () => {
		expect(groups().map((group) => group.hideLabel)).toEqual([true, false, false, false, true, true]);
	});

	it("drops a group with no view in it", () => {
		const only = VIEWS.filter((one) => one.layer !== "site" && one.layer !== "app");
		expect(groups({ views: only }).map((group) => group.group)).toEqual(["Types", "My views", "View", "Default"]);
	});

	it("lists each layer's views in the order the server gave them", () => {
		expect(groups()[1].options.map((one) => one.label)).toEqual(["Mine", "Mine-too"]);
	});

	it("selects the open view and no other", () => {
		const selected = groups({ current: "shared" }).flatMap((group) => group.options.filter((one) => one.selected));
		expect(selected.map((one) => one.label)).toEqual(["Shared"]);
	});

	it("gives each view its type's icon, drawn from the sprite by its bare name", () => {
		const drawn = (label: string) => (row(groups(), label).icon as any)({}, { attrs: { class: "x" } }).props;
		expect(drawn("Cards")).toMatchObject({ name: "layout-grid", class: "x" });
		expect(drawn("Mine")).toMatchObject({ name: "list" });
		expect(drawn("Kanban")).toMatchObject({ name: "kanban" });
	});

	it("shows a loading row until the first read lands", () => {
		expect(viewMenu(host({ views: null }).menu)).toEqual([{ label: "Loading views…", disabled: true }]);
	});
});

describe("the menu while the sidebar lists the views", () => {
	const acts = (over: Partial<ViewMenuHost> = {}) => groups({ listsViews: false, ...over });

	it("holds the open view's acts and no list of views", () => {
		expect(acts().map((group) => group.group)).toEqual(["View", "Default"]);
		expect(labels(acts())).not.toEqual(expect.arrayContaining(["Cards", "Shared", "Kanban"]));
	});

	it("runs the same acts as the full menu", () => {
		const full = groups().filter((group) => ["View", "Default"].includes(group.group));
		expect(labels(acts())).toEqual(labels(full));
	});

	it("keeps Save as new for a plain list with changes", () => {
		const list = acts({ current: "list", plainModified: true });
		expect(list[0].options.map((one) => one.label)).toEqual(["Save as new view…"]);
	});

	it("is unchanged when the host does not say", () => {
		expect(groups().map((group) => group.group)).toContain("Types");
		expect(groups({ listsViews: true }).map((group) => group.group)).toContain("Types");
	});
});

describe("viewLayers", () => {
	it("keeps the four layers in order, empty ones too, with the unbuilt types under Types", () => {
		const layers = viewLayers(VIEWS, SOON);
		expect(layers.map((one) => one.label)).toEqual(["Types", "My views", "Site views", "App views"]);
		expect(layers.map((one) => one.views.map((view) => view.key))).toEqual([
			["list", "cards"],
			["mine", "mine-too"],
			["shared"],
			["app-open"],
		]);
		expect(layers.map((one) => one.soon.length)).toEqual([2, 0, 0, 0]);
		expect(viewLayers([], SOON)[1].views).toEqual([]);
	});
});

describe("the Types group and its Soon rows", () => {
	const types = () => groups()[0].options;

	it("lists the built types, then Kanban, Calendar, Tree and Report as they are kept", () => {
		expect(types().map((one) => one.label)).toEqual(["List", "Cards", "Kanban", "Calendar"]);
	});

	it("draws a Soon badge on each unbuilt type and none on a built one", () => {
		const suffix = (one: Row) => one.slots.suffix?.();
		expect(suffix(types()[1])).toBeUndefined();
		expect(JSON.stringify(suffix(types()[2]).children)).toContain("Soon");
	});

	it("does not disable a Soon row: it opens its type's page like any type row", () => {
		const { menu, run } = host();
		const soon = (viewMenu(menu) as unknown as Group[])[0].options[2];
		expect(soon.disabled).toBeUndefined();
		soon.onClick();
		expect(run).toHaveBeenCalledWith("open_view", { key: "kanban" });
	});

	it("shows no dropped type: Gantt, Inbox, Map and Dashboard stay out", () => {
		expect(labels(groups())).not.toEqual(expect.arrayContaining(["Gantt"]));
		expect(labels(groups()).filter((name) => ["Gantt", "Inbox", "Map", "Dashboard"].includes(name))).toEqual([]);
	});
});

describe("the Default label", () => {
	it("sits on the view the person's bare address opens, and on no other", () => {
		const list = groups();
		const marked = list.flatMap((group) => group.options).filter((one) => one.slots?.suffix);
		const defaults = marked.filter((one) => JSON.stringify(one.slots.suffix().children) === '"Default"');
		expect(defaults.map((one) => one.label)).toEqual(["List"]);
	});

	it("moves to a saved view when the server names it the default", () => {
		const views = VIEWS.map((one) => ({ ...one, default: one.key === "shared" }));
		const defaults = (viewMenu(host({ views }).menu) as unknown as Group[])
			.flatMap((group) => group.options)
			.filter((one) => one.slots?.suffix && JSON.stringify(one.slots.suffix().children) === '"Default"');
		expect(defaults.map((one) => one.label)).toEqual(["Shared"]);
	});
});

describe("the acts each person sees", () => {
	const alone = (key: string, layer: ListedView["layer"], extra: Partial<ListedView> = {}) => ({
		views: [view("list", null), view(key, layer, extra)],
		current: key,
	});

	it("gives a person their own view Rename, Delete and a default of their own", () => {
		expect(actLabels(alone("mine", "own"))).toEqual(["Rename", "Delete", "Set as my default"]);
	});

	it("gives a site administrator Publish on their own view, and a site default that waits for it", () => {
		const list = groups({ ...alone("mine", "own"), admin: true });
		expect(labels(list.filter((group) => ["View", "Default"].includes(group.group)))).toEqual([
			"Rename",
			"Publish to site",
			"Delete",
			"Set as my default",
			"Set as default for everyone",
		]);
		const site = row(list, "Set as default for everyone");
		expect(site.disabled).toBe(true);
		expect(site.description).toBe("Publish this view first");
	});

	it("gives anyone but a site administrator only their own default on a site view", () => {
		expect(actLabels(alone("shared", "site"))).toEqual(["Set as my default"]);
	});

	it("gives a site administrator Rename, Delete and both defaults on a site view", () => {
		expect(actLabels({ ...alone("shared", "site"), admin: true })).toEqual([
			"Rename",
			"Delete",
			"Set as my default",
			"Set as default for everyone",
		]);
	});

	it("keeps an app's view from Rename and Delete, whoever asks", () => {
		expect(actLabels(alone("app-open", "app"))).toEqual(["Set as my default"]);
		expect(actLabels({ ...alone("app-open", "app"), admin: true })).toEqual([
			"Set as my default",
			"Set as default for everyone",
		]);
	});

	it("gives a site administrator Restore, not Delete, on a site row over an app's view", () => {
		const over = alone("app-open", "site", { overrides_app: true });
		expect(actLabels({ ...over, admin: true })).toEqual([
			"Rename",
			"Restore the app's view",
			"Set as my default",
			"Set as default for everyone",
		]);
		expect(actLabels(over)).toEqual(["Set as my default"]);
	});

	it("gives a type's plain view the defaults and nothing to rename, publish or delete", () => {
		expect(actLabels({ views: VIEWS, current: "cards", admin: true })).toEqual([
			"Set as my default",
			"Set as default for everyone",
		]);
	});

	it("offers Remove at the layer that holds the default, and Set at the other", () => {
		const mine = alone("shared", "site", { default_for: ["user"] });
		expect(actLabels(mine)).toEqual(["Remove my default"]);
		const both = { ...alone("shared", "site", { default_for: ["user", "site"] }), admin: true };
		expect(actLabels(both)).toEqual(["Rename", "Delete", "Remove my default", "Remove default for everyone"]);
		const site = { ...alone("shared", "site", { default_for: ["site"] }), admin: true };
		expect(actLabels(site)).toEqual(["Rename", "Delete", "Set as my default", "Remove default for everyone"]);
	});

	it("offers no Remove to someone who cannot change the site's default", () => {
		expect(actLabels(alone("shared", "site", { default_for: ["site"] }))).toEqual(["Set as my default"]);
	});

	it("shows no acts for a view the list does not hold, such as an unbuilt type's page", () => {
		expect(actLabels({ current: "kanban" })).toEqual([]);
	});

	it("takes away the row of an act the page does not draw", () => {
		const list = actLabels({ ...alone("mine", "own"), drawn: (name) => name !== "delete_view" });
		expect(list).toEqual(["Rename", "Set as my default"]);
	});

	it("tells a site administrator from everyone else by role", () => {
		expect(isSiteAdmin(["Sales User"])).toBe(false);
		expect(isSiteAdmin(["Sales User", "System Manager"])).toBe(true);
	});

	it("never offers Delete and Restore together", () => {
		for (const layer of ["own", "site", "app"] as const)
			for (const overrides_app of [false, true])
				for (const admin of [false, true]) {
					const acts = actsOn(view("x", layer, { overrides_app }), admin);
					expect(acts.includes("delete") && acts.includes("restore")).toBe(false);
				}
	});
});

describe("what a row does", () => {
	const only = (key: string, layer: ListedView["layer"], extra: Partial<ListedView> = {}) => ({
		views: [view("list", null), view(key, layer, extra)],
		current: key,
	});

	it("marks every row with the act it runs", () => {
		const list = groups({ ...only("mine", "own"), admin: true, plainModified: false });
		const rows = list.flatMap((group) => group.options);
		expect(rows.every((one) => String(mark(one)["data-act"]).startsWith("list."))).toBe(true);
		expect(mark(row(list, "Rename"))["data-act"]).toBe("list.rename_view");
		expect(mark(row(list, "List"))["data-act"]).toBe("list.open_view");
	});

	it("opens a view by its key", () => {
		const { menu, run } = host();
		row(viewMenu(menu) as unknown as Group[], "Shared").onClick();
		expect(run).toHaveBeenCalledWith("open_view", { key: "shared" });
	});

	it("asks before Rename, Publish, Delete and Restore, naming the view", () => {
		const own = host({ ...only("mine", "own"), admin: true });
		const list = viewMenu(own.menu) as unknown as Group[];
		for (const [label, kind] of [["Rename", "rename"], ["Publish to site", "publish"], ["Delete", "delete"]] as const) {
			row(list, label).onClick();
			expect(own.ask).toHaveBeenLastCalledWith({ kind, view: expect.objectContaining({ key: "mine" }) });
		}
		expect(own.run).not.toHaveBeenCalled();

		const over = host({ ...only("app-open", "site", { overrides_app: true }), admin: true });
		row(viewMenu(over.menu) as unknown as Group[], "Restore the app's view").onClick();
		expect(over.ask).toHaveBeenCalledWith({ kind: "restore", view: expect.objectContaining({ key: "app-open" }) });
	});

	it("runs the default acts at once, with the view and the scope", () => {
		const { menu, run } = host({ ...only("shared", "site", { default_for: ["user"] }), admin: true });
		const list = viewMenu(menu) as unknown as Group[];
		row(list, "Remove my default").onClick();
		expect(run).toHaveBeenLastCalledWith("clear_default_view", { scope: "user" });
		row(list, "Set as default for everyone").onClick();
		expect(run).toHaveBeenLastCalledWith("set_default_view", { key: "shared", scope: "site" });
	});

	it("leads with Save as new view on a plain view that has changes", () => {
		const changed = groups({ ...only("list", null), current: "list", plainModified: true });
		expect(changed[0].options.map((one) => one.label)).toEqual(["Save as new view…"]);
		expect(mark(changed[0].options[0])["data-act"]).toBe("list.save_view_as");
		expect(groups({ current: "list", plainModified: false })[0].group).toBe("Types");
	});

	it("leaves Save as new view to the save bar on a saved view, and on a page that does not draw it", () => {
		expect(labels(groups({ current: "mine", plainModified: true }))).not.toContain("Save as new view…");
		expect(
			labels(groups({ current: "list", plainModified: true, drawn: (name) => name !== "save_view_as" }))
		).not.toContain("Save as new view…");
	});
});

describe("picking a view", () => {
	const push = vi.fn();
	const router = { push } as unknown as Router;

	beforeEach(() => {
		push.mockReset();
		clearSkip();
		const addresses = new Addresses({ doctypes: { ToDo: ["todo", "desk"] }, modules: { desk: "Desk" } });
		const boot = { app: "frappe", shell_base: "/desk", prefixes: { frappe: { app: "frappe", modular: false } } } as unknown as Boot;
		registerShell({ boot, addresses, router });
	});

	it("opens the bare address for the List type and skips the default for that one visit", () => {
		openView(router, "ToDo", "list");
		expect(push).toHaveBeenCalledWith(expect.objectContaining({ params: expect.anything() }));
		expect(consumeSkip("ToDo")).toBe(true);
		expect(consumeSkip("ToDo")).toBe(false);
	});

	it("opens another type or a saved view at /view/<key>, with nothing skipped", () => {
		openView(router, "ToDo", "cards");
		openView(router, "ToDo", "kanban");
		openView(router, "ToDo", "mine");
		const keys = push.mock.calls.map(([to]) => to.params?.key ?? to.params?.view);
		expect(keys).toEqual(["cards", "kanban", "mine"]);
		expect(consumeSkip("ToDo")).toBe(false);
	});
});
