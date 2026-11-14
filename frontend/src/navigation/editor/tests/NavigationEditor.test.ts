// The editor, mounted: it reads a level, edits a draft, and commits with one Save.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick, ref } from "vue";
import { createWebHistory, createRouter, type Router } from "vue-router";

import { ApiError } from "@framework/ui/api";
import type { Boot } from "@/boot";
import type { Arrangements, EditorRow } from "../draft";
import { resetSprite } from "@/icons/sprite";
import NavigationEditor from "../NavigationEditor.vue";

const api = vi.hoisted(() => ({
	fetchArrangements: vi.fn(),
	fetchDefaultArrangements: vi.fn(),
	saveArrangements: vi.fn(),
	saveNavigationLayout: vi.fn(),
}));
vi.mock("@/arrangement", () => api);

const confirm = vi.hoisted(() => vi.fn());
vi.mock("frappe-ui", async (original) => ({
	...(await original<object>()),
	dialog: { confirm },
}));

const row = (key: string, more: Partial<EditorRow> = {}): EditorRow => ({
	key,
	item_type: "DocType",
	link_to: key,
	label: key.toUpperCase(),
	...more,
});

function response(more: Partial<Arrangements> = {}): Arrangements {
	return {
		version: "v1",
		can_edit_site: true,
		has_saved: false,
		navigation_layouts: { standard: "", site: "", user: "" },
		rail: [row("todo"), row("note", { hidden: 1 })],
		sidebars: {},
		...more,
	};
}

async function settle() {
	for (let turn = 0; turn < 4; turn++) {
		await new Promise((resolve) => setTimeout(resolve, 0));
		await nextTick();
	}
}

const body = () => document.body;
const text = (selector: string) => body().querySelector(selector)?.textContent?.trim();
const rowsShown = () => Array.from(body().querySelectorAll("[data-editor-list] li")).map((li) => li.textContent?.trim());

let unmount = () => {};
let router: Router;

async function open(answer: Arrangements = response()) {
	api.fetchArrangements.mockResolvedValue(answer);
	const emitted: string[] = [];
	const app = createApp(NavigationEditor, {
		target: { tab: "rail" },
		onClose: () => emitted.push("close"),
		onSaved: () => emitted.push("saved"),
	});
	app.provide("boot", { app: "crm", app_title: "CRM" } as unknown as Boot);
	router = createRouter({ history: createWebHistory(), routes: [{ path: "/:rest(.*)*", component: { render: () => null } }] });
	await router.push("/page");
	await router.push("/page#customize/rail");
	app.use(router);
	const host = document.createElement("div");
	document.body.appendChild(host);
	app.mount(host);
	unmount = () => app.unmount();
	await settle();
	return emitted;
}

const click = (selector: string) => body().querySelector<HTMLElement>(selector)!.click();

beforeEach(() => {
	document.body.innerHTML = "";
	Object.values(api).forEach((fn) => fn.mockReset());
	confirm.mockReset();
});
afterEach(() => {
	unmount();
	vi.unstubAllGlobals();
});

describe("the editor", () => {
	it("marks only the rows the level itself added, a site row is inherited at Just me", async () => {
		await open(response({ rail: [row("todo"), row("site:wiki"), row("user:mine")] }));
		expect(rowsShown()).toEqual(["TODO", "SITE:WIKI", "USER:MINEAdded"]);
		click("[data-key='site:wiki']");
		await settle();
		expect(text("[data-editor-pane]")).toContain("You can rename it, change its icon");
		click("[data-key='user:mine']");
		await settle();
		expect(text("[data-editor-pane]")).not.toContain("You can rename it, change its icon");
	});

	it("reads the level and lists the rail, hidden rows only on request", async () => {
		await open();
		expect(text("[data-navigation-editor] h2")).toBe("Customize navigation");
		expect(rowsShown()).toEqual(["TODO"]);

		body().querySelector<HTMLInputElement>("input[type='checkbox']")!.click();
		await settle();
		expect(rowsShown()).toEqual(["TODO", "NOTEHidden"]);
	});

	it("keeps Save disabled until an edit, then saves the rows and closes", async () => {
		api.saveArrangements.mockResolvedValue({ rail: [], sidebars: {} });
		const emitted = await open();
		expect(body().querySelector<HTMLButtonElement>("[data-save]")!.disabled).toBe(true);

		click("[data-key='todo']");
		await settle();
		expect(text("[data-editor-pane] p")).toBe("TODO");
		const label = body().querySelector<HTMLInputElement>("[data-field='label'] input, input[data-field='label']")!;
		label.value = "Tasks";
		label.dispatchEvent(new Event("input", { bubbles: true }));
		await settle();
		expect(body().querySelector<HTMLButtonElement>("[data-save]")!.disabled).toBe(false);

		click("[data-save]");
		await settle();
		expect(api.saveArrangements).toHaveBeenCalledOnce();
		const [app, scope, payload, version] = api.saveArrangements.mock.calls[0];
		expect([app, scope, version]).toEqual(["crm", "user", "v1"]);
		expect(payload.rail[0].label).toBe("Tasks");
		expect(api.saveNavigationLayout).not.toHaveBeenCalled();
		expect(emitted).toEqual(["saved", "close"]);
	});

	it("sets a row's icon from the picker into the draft", async () => {
		resetSprite();
		vi.stubGlobal(
			"fetch",
			vi.fn().mockResolvedValue({
				ok: true,
				text: () => Promise.resolve('<svg><symbol id="icon-star"></symbol></svg>'),
			})
		);
		api.saveArrangements.mockResolvedValue({ rail: [], sidebars: {} });
		await open();
		click("[data-key='todo']");
		await settle();

		const trigger = body().querySelector<HTMLElement>("[data-field='icon'] button")!;
		trigger.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, button: 0 }));
		trigger.click();
		await settle();
		const star = [...document.querySelectorAll<HTMLElement>('[role="option"]')].find(
			(option) => option.textContent?.trim() === "star"
		)!;
		star.click();
		await settle();
		click("[data-save]");
		await settle();

		expect(api.saveArrangements.mock.calls[0][2].rail[0].icon).toBe("star");
	});

	it("hides a row from the pane's Hide button", async () => {
		await open();
		click("[data-key='todo']");
		await settle();
		click("[data-row-actions] button");
		await settle();
		expect(rowsShown()).toEqual([]);
		expect(body().querySelector("[data-revert]")).not.toBeNull();
	});

	it("offers Reset to default only when this level has saved, and Save commits it", async () => {
		await open();
		expect(body().querySelector("[data-reset]")).toBeNull();
		unmount();
		document.body.innerHTML = "";

		api.fetchDefaultArrangements.mockResolvedValue({ rail: [row("todo")], sidebars: {} });
		api.saveArrangements.mockResolvedValue({ rail: [], sidebars: {} });
		await open(response({ has_saved: true, rail: [row("todo"), row("user:abc123")] }));

		click("[data-reset]");
		await settle();
		expect(api.fetchDefaultArrangements).toHaveBeenCalledWith("crm", "user");
		expect(rowsShown()).toEqual(["TODO"]);
		expect(body().querySelector("[data-reset]")).toBeNull();

		click("[data-save]");
		await settle();
		expect(api.saveArrangements.mock.calls[0][2].rail.map((r: EditorRow) => r.key)).toEqual(["todo"]);
	});

	it("shows the error and a Reload on a stale version", async () => {
		const stale = new ApiError({ type: "TimestampMismatchError", message: "Changed meanwhile" }, 417);
		api.saveArrangements.mockRejectedValue(stale);
		await open();
		click("[data-key='todo']");
		await settle();
		click("[data-row-actions] button");
		await settle();
		click("[data-save]");
		await settle();
		expect(text("[data-save-error]")).toContain("Changed meanwhile");
		expect(body().querySelector("[data-save-error] button")?.textContent?.trim()).toBe("Reload");
	});

	it("asks before a Reload drops a draft with edits, and reads only when told to discard", async () => {
		const stale = new ApiError({ type: "TimestampMismatchError", message: "Changed meanwhile" }, 417);
		api.saveArrangements.mockRejectedValue(stale);
		await open();
		click("[data-key='todo']");
		await settle();
		click("[data-row-actions] button");
		await settle();
		click("[data-save]");
		await settle();

		api.fetchArrangements.mockResolvedValue(response({ version: "v2", rail: [row("other")] }));
		const reads = api.fetchArrangements.mock.calls.length;
		click("[data-save-error] button");
		await settle();
		expect(confirm).toHaveBeenCalledOnce();
		expect(api.fetchArrangements).toHaveBeenCalledTimes(reads);
		expect(body().querySelector("[data-revert]")).not.toBeNull();

		const { actions } = confirm.mock.calls[0][0];
		expect(actions.map((action: { label: string; variant: string }) => [action.label, action.variant])).toEqual([
			["Keep editing", "subtle"],
			["Discard and reload", "subtle"],
		]);
		expect(actions[0].onClick).toBeUndefined();
		actions[1].onClick();
		await settle();
		expect(api.fetchArrangements).toHaveBeenCalledTimes(reads + 1);
		expect(rowsShown()).toEqual(["OTHER"]);
		expect(body().querySelector("[data-save-error]")).toBeNull();
	});

	it("reloads at once when the draft has no edits left", async () => {
		const stale = new ApiError({ type: "TimestampMismatchError", message: "Changed meanwhile" }, 417);
		api.saveArrangements.mockRejectedValue(stale);
		await open();
		click("[data-key='todo']");
		await settle();
		click("[data-row-actions] button");
		await settle();
		click("[data-save]");
		await settle();
		click("[data-revert]");
		await settle();

		api.fetchArrangements.mockResolvedValue(response({ version: "v2", rail: [row("other")] }));
		click("[data-save-error] button");
		await settle();
		expect(confirm).not.toHaveBeenCalled();
		expect(rowsShown()).toEqual(["OTHER"]);
	});

	describe("leaving with edits", () => {
		const hide = async () => {
			click("[data-key='todo']");
			await settle();
			click("[data-row-actions] button");
			await settle();
		};
		const labels = () =>
			confirm.mock.calls[0][0].actions.map((action: { label: string }) => action.label);

		it("asks before Cancel drops edits, and closes only on Discard", async () => {
			const emitted = await open();
			await hide();
			click("footer button:not([data-save]):not([data-revert])");
			await settle();
			expect(confirm).toHaveBeenCalledOnce();
			expect(confirm.mock.calls[0][0].title).toBe("Discard your changes?");
			expect(labels()).toEqual(["Keep editing", "Discard and close"]);
			expect(emitted).toEqual([]);

			confirm.mock.calls[0][0].actions[1].onClick();
			expect(emitted).toEqual(["close"]);
		});

		it("closes Cancel at once when nothing changed", async () => {
			const emitted = await open();
			click("footer button:not([data-save]):not([data-revert])");
			await settle();
			expect(confirm).not.toHaveBeenCalled();
			expect(emitted).toEqual(["close"]);
		});

		it("keeps Back on the editor until Discard, then lets it through", async () => {
			await open();
			await hide();
			router.back();
			await settle();
			expect(confirm).toHaveBeenCalledOnce();
			expect(router.currentRoute.value.hash).toBe("#customize/rail");
			expect(body().querySelector("[data-save]")).not.toBeNull();

			const editorEntry = router.options.history.state.position;
			confirm.mock.calls[0][0].actions[1].onClick();
			await settle();
			expect(router.currentRoute.value.hash).toBe("");
			expect(router.options.history.state.position).toBe((editorEntry as number) - 1);
		});

		it("lets no exit through while a save runs", async () => {
			api.saveArrangements.mockReturnValue(new Promise(() => {}));
			await open();
			await hide();
			click("[data-save]");
			await settle();
			await router.replace({ hash: "" });
			expect(confirm).not.toHaveBeenCalled();
			expect(router.currentRoute.value.hash).toBe("#customize/rail");
		});

		it("replaces the open confirm when Back is pressed again", async () => {
			const first = { close: vi.fn() };
			confirm.mockReturnValueOnce(first);
			await open();
			await hide();
			router.back();
			await settle();
			await router.replace({ hash: "" });
			await settle();
			expect(confirm).toHaveBeenCalledTimes(2);
			expect(first.close).toHaveBeenCalledOnce();
		});

		it("asks again after a close navigation that another guard refused", async () => {
			await open();
			await hide();
			const refuse = router.beforeEach((to) => (to.hash === "" ? false : undefined));
			router.back();
			await settle();
			confirm.mock.calls[0][0].actions[1].onClick();
			await settle();
			expect(router.currentRoute.value.hash).toBe("#customize/rail");
			refuse();

			await router.replace({ hash: "" });
			await settle();
			expect(confirm).toHaveBeenCalledTimes(2);
			expect(router.currentRoute.value.hash).toBe("#customize/rail");
		});

		it("asks before a hash change closes the editor, and leaves a clean one alone", async () => {
			await open();
			await hide();
			await router.replace({ hash: "" });
			await settle();
			expect(confirm).toHaveBeenCalledOnce();
			expect(router.currentRoute.value.hash).toBe("#customize/rail");

			click("[data-revert]");
			await settle();
			await router.replace({ hash: "" });
			expect(confirm).toHaveBeenCalledOnce();
			expect(router.currentRoute.value.hash).toBe("");
		});

		it("asks before a move to another editor hash reloads the draft", async () => {
			await open();
			await hide();
			await router.replace({ hash: "#customize/sidebar/side" });
			await settle();
			expect(confirm).toHaveBeenCalledOnce();
			expect(router.currentRoute.value.hash).toBe("#customize/rail");
		});

		it("does not ask when a Save closes the editor", async () => {
			api.saveArrangements.mockResolvedValue({ rail: [], sidebars: {} });
			const emitted = await open();
			await hide();
			click("[data-save]");
			await settle();
			expect(emitted).toContain("close");
			await router.replace({ hash: "" });
			expect(confirm).not.toHaveBeenCalled();
			expect(router.currentRoute.value.hash).toBe("");
		});

		it("keeps the edits when the person chooses Keep editing", async () => {
			const emitted = await open();
			await hide();
			click("footer button:not([data-save]):not([data-revert])");
			await settle();
			expect(confirm.mock.calls[0][0].actions[0].onClick).toBeUndefined();
			expect(emitted).toEqual([]);
			expect(body().querySelector("[data-revert]")).not.toBeNull();
		});
	});


	it("moves focus from a row to the form on Enter", async () => {
		await open(response({ rail: [row("todo"), row("note")] }));
		const item = body().querySelector<HTMLElement>("[data-key='note']")!;
		item.focus();
		item.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
		await settle();
		const label = body().querySelector("[data-editor-pane] input[data-field='label'], [data-editor-pane] [data-field='label'] input");
		expect(label).not.toBeNull();
		expect(document.activeElement).toBe(label);
	});

	it("keeps the new version and the layout edit when the layout save fails after the rows", async () => {
		api.saveArrangements.mockResolvedValue({ rail: [], sidebars: {} });
		api.saveNavigationLayout.mockRejectedValue(new Error("No layout"));
		// Reset to default changes the rows and clears the layout: two saves.
		api.fetchDefaultArrangements.mockResolvedValue({ rail: [row("todo")], sidebars: {} });
		const emitted = await open(
			response({
				has_saved: true,
				navigation_layouts: { standard: "", site: "", user: "sidebar_only" },
				rail: [row("todo"), row("user:abc123")],
			})
		);
		click("[data-reset]");
		await settle();

		api.fetchArrangements.mockResolvedValue(
			response({
				version: "v2",
				has_saved: true,
				navigation_layouts: { standard: "", site: "", user: "sidebar_only" },
				rail: [row("todo")],
			})
		);
		click("[data-save]");
		await settle();
		expect(api.saveNavigationLayout).toHaveBeenCalledOnce();
		expect(emitted).toEqual(["saved"]);
		expect(text("[data-save-error]")).toContain("Your rows are saved, but the layout is not: No layout");

		// Save again: the layout alone goes out, and the rows are not sent on the old version.
		api.saveNavigationLayout.mockResolvedValue({ rail: [], sidebars: {} });
		click("[data-save]");
		await settle();
		expect(api.saveArrangements).toHaveBeenCalledOnce();
		expect(api.saveNavigationLayout).toHaveBeenCalledTimes(2);
		expect(api.saveNavigationLayout.mock.calls[1][1]).toBe("");
		expect(emitted).toEqual(["saved", "saved", "close"]);
	});

	it("hands the selection to the next visible row when the selected one is hidden", async () => {
		await open(response({ rail: [row("a"), row("b", { hidden: 1 }), row("c")] }));
		click("[data-key='a']");
		await settle();
		click("[data-row-actions] button");
		await settle();
		expect(text("[data-editor-pane] p")).toBe("C");
		expect(body().querySelector("[data-key='c']")!.getAttribute("tabindex")).toBe("0");
	});

	it("lets a nested row sit two levels in", async () => {
		await open(
			response({
				rail: [
					row("s", { item_type: "Section" }),
					row("i", { parent_key: "s" }),
					row("c", { parent_key: "i" }),
				],
			})
		);
		const guides = (key: string) => body().querySelectorAll(`[data-key='${key}'] > span.w-4`).length;
		expect([guides("s"), guides("i"), guides("c")]).toEqual([0, 1, 2]);
	});

	it("keeps the Sidebar tab when the editor is opened again on a sidebar", async () => {
		api.fetchArrangements.mockResolvedValue(
			response({
				rail: [row("crm", { item_type: "Sidebar", link_to: "s1" })],
				sidebars: { s1: [row("lead")] },
			})
		);
		const target = ref<{ tab: "sidebar"; address: string }>({ tab: "sidebar", address: "s1" });
		const app = createApp({ render: () => h(NavigationEditor, { target: target.value }) });
		app.provide("boot", { app: "crm", app_title: "CRM" } as unknown as Boot);
	router = createRouter({ history: createWebHistory(), routes: [{ path: "/:rest(.*)*", component: { render: () => null } }] });
	await router.push("/page");
	await router.push("/page#customize/rail");
	app.use(router);
		const host = document.createElement("div");
		document.body.appendChild(host);
		app.mount(host);
		unmount = () => app.unmount();
		await settle();
		expect(rowsShown()).toEqual(["LEAD"]);

		target.value = { tab: "sidebar", address: "s1" };
		await settle();
		expect(rowsShown()).toEqual(["LEAD"]);
	});

	it("does not let the level change while Reset to default is on its way", async () => {
		let answer!: (defaults: { rail: EditorRow[]; sidebars: {} }) => void;
		api.fetchDefaultArrangements.mockReturnValue(new Promise((resolve) => (answer = resolve)));
		await open(response({ has_saved: true }));

		click("[data-reset]");
		await nextTick();
		const everyone = Array.from(body().querySelectorAll<HTMLButtonElement>("[data-level-switch] button")).find(
			(button) => button.textContent?.trim() === "Everyone"
		);
		expect(everyone?.disabled).toBe(true);

		// The draft cannot take an edit or a Save until the reset lands.
		expect(body().querySelector("[data-editor-pane]")?.closest("[inert]")).not.toBeNull();
		expect(body().querySelector<HTMLButtonElement>("[data-save]")!.disabled).toBe(true);

		answer({ rail: [row("todo")], sidebars: {} });
		await settle();
		expect(rowsShown()).toEqual(["TODO"]);
	});

	it("moves to a sidebar the other level opens when the level changes", async () => {
		const sidebars = (key: string, lead: string) => ({
			rail: [row("crm", { item_type: "Sidebar", link_to: key })],
			sidebars: { [key]: [row(lead)] },
		});
		api.fetchArrangements
			.mockResolvedValueOnce(response(sidebars("mine", "lead")))
			.mockResolvedValueOnce(response(sidebars("shared", "deal")));
		const app = createApp({ render: () => h(NavigationEditor, { target: { tab: "sidebar", address: "mine" } }) });
		app.provide("boot", { app: "crm", app_title: "CRM" } as unknown as Boot);
	router = createRouter({ history: createWebHistory(), routes: [{ path: "/:rest(.*)*", component: { render: () => null } }] });
	await router.push("/page");
	await router.push("/page#customize/rail");
	app.use(router);
		const host = document.createElement("div");
		document.body.appendChild(host);
		app.mount(host);
		unmount = () => app.unmount();
		await settle();
		expect(rowsShown()).toEqual(["LEAD"]);

		const level = (label: string) =>
			Array.from(body().querySelectorAll<HTMLButtonElement>("[data-level-switch] button")).find(
				(button) => button.textContent?.trim() === label
			)!;
		level("Everyone").click();
		await settle();
		expect(rowsShown()).toEqual(["DEAL"]);

		level("Just me").click();
		await settle();
		expect(rowsShown()).toEqual(["LEAD"]);
	});

	it("ignores a read that comes back after the editor was opened again", async () => {
		let late!: (answer: Arrangements) => void;
		api.fetchArrangements
			.mockReturnValueOnce(new Promise((resolve) => (late = resolve)))
			.mockResolvedValueOnce(response({ rail: [row("fresh")] }));
		const target = ref<{ tab: "rail" }>({ tab: "rail" });
		const app = createApp({ render: () => h(NavigationEditor, { target: target.value }) });
		app.provide("boot", { app: "crm", app_title: "CRM" } as unknown as Boot);
	router = createRouter({ history: createWebHistory(), routes: [{ path: "/:rest(.*)*", component: { render: () => null } }] });
	await router.push("/page");
	await router.push("/page#customize/rail");
	app.use(router);
		const host = document.createElement("div");
		document.body.appendChild(host);
		app.mount(host);
		unmount = () => app.unmount();
		await settle();

		target.value = { tab: "rail" };
		await settle();
		expect(rowsShown()).toEqual(["FRESH"]);

		late(response({ rail: [row("stale")] }));
		await settle();
		expect(rowsShown()).toEqual(["FRESH"]);
	});

	it("keeps the newest read of a level when an older read of it lands last", async () => {
		let first!: (answer: Arrangements) => void;
		await open();
		api.fetchArrangements
			.mockReturnValueOnce(new Promise((resolve) => (first = resolve)))
			.mockResolvedValueOnce(response({ rail: [row("second")] }));
		const level = (label: string) =>
			Array.from(body().querySelectorAll<HTMLButtonElement>("[data-level-switch] button")).find(
				(button) => button.textContent?.trim() === label
			)!;

		level("Everyone").click();
		await settle();
		level("Just me").click();
		await settle();
		level("Everyone").click();
		await settle();
		expect(api.fetchArrangements).toHaveBeenCalledTimes(3);
		expect(rowsShown()).toEqual(["SECOND"]);

		first(response({ rail: [row("first")] }));
		await settle();
		expect(rowsShown()).toEqual(["SECOND"]);
	});

	it("leaves a reopened editor alone when a save of the earlier opening ends late", async () => {
		let rowsSaved!: (navigation: unknown) => void;
		api.saveArrangements.mockReturnValue(new Promise((resolve) => (rowsSaved = resolve)));
		api.saveNavigationLayout.mockRejectedValue(new Error("No layout"));
		api.fetchDefaultArrangements.mockResolvedValue({ rail: [row("todo")], sidebars: {} });
		api.fetchArrangements.mockResolvedValue(
			response({
				has_saved: true,
				navigation_layouts: { standard: "", site: "", user: "sidebar_only" },
				rail: [row("todo"), row("user:abc123")],
			})
		);
		const emitted: string[] = [];
		const target = ref<{ tab: "rail" }>({ tab: "rail" });
		const app = createApp({
			render: () =>
				h(NavigationEditor, {
					target: target.value,
					onClose: () => emitted.push("close"),
					onSaved: () => emitted.push("saved"),
				}),
		});
		app.provide("boot", { app: "crm", app_title: "CRM" } as unknown as Boot);
	router = createRouter({ history: createWebHistory(), routes: [{ path: "/:rest(.*)*", component: { render: () => null } }] });
	await router.push("/page");
	await router.push("/page#customize/rail");
	app.use(router);
		const host = document.createElement("div");
		document.body.appendChild(host);
		app.mount(host);
		unmount = () => app.unmount();
		await settle();

		// Reset to default changes the rows and the layout: the save goes out in two calls.
		click("[data-reset]");
		await settle();
		click("[data-save]");
		await nextTick();

		// The editor opens again while that save is on its way, and the new draft takes an edit.
		api.fetchArrangements.mockResolvedValue(response({ rail: [row("fresh"), row("other")] }));
		target.value = { tab: "rail" };
		await settle();
		click("[data-key='fresh']");
		await settle();
		click("[data-row-actions] button");
		await settle();
		expect(rowsShown()).toEqual(["OTHER"]);
		const reads = api.fetchArrangements.mock.calls.length;

		rowsSaved({ rail: [], sidebars: {} });
		await settle();
		expect(api.saveNavigationLayout).toHaveBeenCalledOnce();
		expect(api.fetchArrangements).toHaveBeenCalledTimes(reads);
		expect(rowsShown()).toEqual(["OTHER"]);
		expect(body().querySelector("[data-revert]")).not.toBeNull();
		expect(body().querySelector("[data-save-error]")).toBeNull();
		expect(body().querySelector<HTMLButtonElement>("[data-save]")!.disabled).toBe(false);
		expect(emitted).toEqual(["saved"]);
	});
});
