// The saved-view acts of `list`: each posts to the server, then moves the page and the views the way the act says.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { computed, ref } from "vue";
import type { Router } from "vue-router";

const runMethod = vi.hoisted(() => vi.fn());
vi.mock("@framework/ui/api", () => ({ runMethod }));

import { ActInvalid } from "@/acts/dispatcher";
import type { Boot } from "@/boot";
import type { ListPage } from "@/list/useListPage";
import type { View } from "@/list/view";
import { Addresses } from "@/addresses";
import { registerShell } from "@/router/routeFor";
import { consumeSkip, clearSkip } from "@/router/skipDefault";
import { refreshSavedViews } from "@/list/savedView";
import { forgetFavouriteView } from "@/list/useListSettings";
import { clearDefaultView } from "../defaultView";
import { RUNS, type ViewWriteHost } from "../viewWriteRuns";

const API = "frappe.desk.doctype.doctype_view.api";
const SETTINGS = { columns: [{ fieldname: "title" }], filters: [], sort: [{ fieldname: "title", direction: "asc" }] };

const addresses = new Addresses({ doctypes: { ToDo: ["todo", "desk"] }, modules: { desk: "Desk" } });
const shellBoot = { app: "frappe", shell_base: "/desk", prefixes: { frappe: { app: "frappe", modular: false } } } as unknown as Boot;

const push = vi.fn();
const replace = vi.fn();
const danger = vi.fn();

function host(over: { layer?: View["layer"]; key?: string; saveable?: boolean; defaults?: Record<string, string> } = {}) {
	const view = {
		doctype: "ToDo",
		key: over.key ?? "mine",
		type: "List",
		layer: over.layer === undefined ? "own" : over.layer,
		saveable: computed(() => over.saveable ?? true),
		modified: ref(true),
	} as unknown as View;
	const page = { view, snapshot: vi.fn(() => SETTINGS), commit: vi.fn(), discard: vi.fn() };
	const boot = { default_views: over.defaults ?? {} } as unknown as Boot;
	const router = { push, replace } as unknown as Router;
	const context: ViewWriteHost = {
		page: page as unknown as ListPage,
		boot,
		router,
		dialog: { danger },
		refreshViews: refreshSavedViews,
		forgetStar: (key) => forgetFavouriteView("ToDo", key),
		refreshDefault: () => clearDefaultView(boot, "ToDo", "user"),
	};
	return { page, boot, router, run: host_run(context) };
}

function host_run(context: ViewWriteHost) {
	return (name: string, value?: unknown, agent?: boolean) => RUNS[name](context, value, agent);
}

beforeEach(() => {
	registerShell({ boot: shellBoot, addresses, router: { push, replace } as unknown as Router });
	runMethod.mockReset().mockResolvedValue({ data: { key: "mine", label: "Mine", layer: "own" } });
	push.mockReset().mockResolvedValue(undefined);
	replace.mockReset().mockResolvedValue(undefined);
	danger.mockReset().mockResolvedValue(true);
	clearSkip();
});

describe("save_view", () => {
	it("posts the page's settings for the open view, then makes them the view's base", async () => {
		const { page, run } = host();
		await run("save_view");
		expect(runMethod).toHaveBeenCalledWith(`${API}.save_view`, { doctype: "ToDo", key: "mine", settings: SETTINGS });
		expect(page.commit).toHaveBeenCalledWith(SETTINGS);
	});

	it("refuses a view type's plain view and points to save_view_as", async () => {
		const { run } = host({ layer: null, key: "list" });
		await expect(run("save_view")).rejects.toThrow(ActInvalid);
		await expect(run("save_view")).rejects.toThrow("list.save_view_as");
		expect(runMethod).not.toHaveBeenCalled();
	});

	it("refuses a shared view the person cannot save, before asking the server", async () => {
		const { run } = host({ layer: "site", saveable: false });
		await expect(run("save_view")).rejects.toThrow("site administrator");
		expect(runMethod).not.toHaveBeenCalled();
	});

	it("keeps the page's changes when the server refuses", async () => {
		runMethod.mockRejectedValue(new Error("no"));
		const { page, run } = host();
		await expect(run("save_view")).rejects.toThrow("no");
		expect(page.commit).not.toHaveBeenCalled();
	});
});

describe("save_view_as", () => {
	it("posts a new view of the open view's type and opens it at its key", async () => {
		runMethod.mockResolvedValue({ data: { key: "my-open", label: "My open" } });
		const { run } = host({ layer: null, key: "list" });

		expect(await run("save_view_as", { label: "My open" })).toEqual({ key: "my-open", label: "My open" });
		expect(runMethod).toHaveBeenCalledWith(`${API}.save_view_as`, {
			doctype: "ToDo",
			label: "My open",
			settings: SETTINGS,
			type: "List",
		});
		expect(push).toHaveBeenCalledWith(expect.objectContaining({ params: expect.objectContaining({ key: "my-open" }) }));
	});
});

describe("discard_changes", () => {
	it("drops the page's changes on a saved view, with no server call", async () => {
		const { page, run } = host();
		await run("discard_changes");
		expect(page.discard).toHaveBeenCalled();
		expect(runMethod).not.toHaveBeenCalled();
	});

	it("refuses a plain view", async () => {
		const { page, run } = host({ layer: null, key: "list" });
		await expect(run("discard_changes")).rejects.toThrow(ActInvalid);
		expect(page.discard).not.toHaveBeenCalled();
	});
});

describe("rename_view and publish_view", () => {
	it("rename posts the key and the new label", async () => {
		runMethod.mockResolvedValue({ data: { key: "mine", label: "Renamed" } });
		const { run } = host();
		expect(await run("rename_view", { key: "mine", label: "Renamed" })).toEqual({ key: "mine", label: "Renamed" });
		expect(runMethod).toHaveBeenCalledWith(`${API}.rename_view`, { doctype: "ToDo", key: "mine", label: "Renamed" });
	});

	it("publish posts the key and answers with the layer it now sits in", async () => {
		runMethod.mockResolvedValue({ data: { key: "mine", layer: "site" } });
		const { run } = host();
		expect(await run("publish_view", { key: "mine" })).toEqual({ key: "mine", layer: "site" });
		expect(runMethod).toHaveBeenCalledWith(`${API}.publish_view`, { doctype: "ToDo", key: "mine" });
	});
});

describe("delete_view", () => {
	it("leaves a deleted open view for the plain list, skipping the default for that visit", async () => {
		runMethod.mockImplementation(async (method: string) => ({
			data: method.endsWith(".clear") ? null : { key: "mine", restored: false },
		}));
		const { boot, run } = host({ defaults: { ToDo: "mine" } });

		expect(await run("delete_view", { key: "mine" })).toEqual({ key: "mine", restored: false });
		expect(replace).toHaveBeenCalled();
		expect((boot as { default_views: object }).default_views).toEqual({});
		expect(consumeSkip("ToDo")).toBe(true);
	});

	it("stays on the page when another view was deleted, and keeps a default that points elsewhere", async () => {
		runMethod.mockResolvedValue({ data: { key: "other", restored: false } });
		const { boot, run } = host({ defaults: { ToDo: "mine" } });

		await run("delete_view", { key: "other" });
		expect(replace).not.toHaveBeenCalled();
		expect((boot as { default_views: object }).default_views).toEqual({ ToDo: "mine" });
	});

	it("stays when a site row over an app's view went: the app's view answers at the key again", async () => {
		runMethod.mockResolvedValue({ data: { key: "mine", restored: true } });
		const { boot, run } = host({ layer: "site", defaults: { ToDo: "mine" } });

		expect(await run("delete_view", { key: "mine" })).toEqual({ key: "mine", restored: true });
		expect(replace).not.toHaveBeenCalled();
		expect((boot as { default_views: object }).default_views).toEqual({ ToDo: "mine" });
	});

	it("takes the default that answers next, from the server, when the person's own default is deleted", async () => {
		runMethod.mockImplementation(async (method: string) => ({
			data: method.endsWith(".clear") ? "site-open" : { key: "mine", restored: false },
		}));
		const { boot, run } = host({ defaults: { ToDo: "mine" } });

		await run("delete_view", { key: "mine" });
		expect(runMethod).toHaveBeenCalledWith(
			"frappe.desk.doctype.default_view.api.clear",
			{ doctype: "ToDo", scope: "user", app: undefined },
			{ nullable: true }
		);
		expect((boot as { default_views: object }).default_views).toEqual({ ToDo: "site-open" });
	});

	it("drops the deleted view from the cached stars, and leaves them when an app's view answers again", async () => {
		const { useListSettings } = await import("@/list/useListSettings");
		runMethod.mockImplementation(async (method: string) => ({
			data: method.endsWith(".get") ? { favourites: { list: false, views: ["mine", "kept"] } } : { key: "mine", restored: false },
		}));
		const settings = useListSettings("ToDo");
		await vi.waitFor(() => expect(settings.favourites.value?.views).toEqual(["mine", "kept"]));

		await host().run("delete_view", { key: "mine" });
		expect(settings.favourites.value?.views).toEqual(["kept"]);

		runMethod.mockResolvedValue({ data: { key: "kept", restored: true } });
		await host({ layer: "site", key: "kept" }).run("delete_view", { key: "kept" });
		expect(settings.favourites.value?.views).toEqual(["kept"]);
	});

	it("asks an agent before it deletes, and a person's script is not asked", async () => {
		runMethod.mockResolvedValue({ data: { key: "other", restored: false } });
		danger.mockResolvedValue(null);
		await expect(host().run("delete_view", { key: "other" }, true)).rejects.toMatchObject({ name: "ActDeclined" });
		expect(runMethod).not.toHaveBeenCalled();

		danger.mockResolvedValue(true);
		await host().run("delete_view", { key: "other" }, true);
		expect(runMethod).toHaveBeenCalledTimes(1);

		danger.mockClear();
		await host().run("delete_view", { key: "other" });
		expect(danger).not.toHaveBeenCalled();
	});
});
