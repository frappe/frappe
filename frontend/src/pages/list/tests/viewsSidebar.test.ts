// The DocType sidebar's body: the views by group, the open one marked, Soon rows for unbuilt types,
// and the crumb told when the rows are really on screen.
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, effectScope, h, nextTick, ref } from "vue";
import { createMemoryHistory, createRouter, type Router } from "vue-router";
import { loadText, TEXT_SURFACES } from "@/acts/actText";
import { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { resetListedViews, type ListedView } from "@/list/listedViews";
import { markModifiedView } from "@/list/modifiedView";
import type { View } from "@/list/view";
import { viewsSidebarDrawn } from "@/navigation/viewsSidebar";
import { registerShell } from "@/router/routeFor";
import { consumeSkip } from "@/router/skipDefault";
import ViewsSidebar from "../viewSwitcher/ViewsSidebar.vue";

beforeAll(() => Promise.all(TEXT_SURFACES.map(loadText)));

const fetchViews = vi.hoisted(() => vi.fn());
vi.mock("@/navigation/editor/viewPicker", () => ({ fetchViews }));
vi.mock("@framework/ui/useSession", () => ({ currentSession: () => ({ user: { name: "a@example.com" } }) }));

const addresses = new Addresses({ doctypes: { ToDo: ["todo", "frappe"] }, modules: { frappe: "Frappe" } });
const stub = { render: () => null };

const VIEWS: ListedView[] = [
	{ key: "list", label: "List", type: "List", layer: null, default: true },
	{ key: "cards", label: "Cards", type: "Cards", layer: null },
	{ key: "mine", label: "Mine", type: "List", layer: "own" },
	{ key: "team", label: "Team", type: "List", layer: "site" },
];

const mounted: ReturnType<typeof createApp>[] = [];
afterEach(() => {
	mounted.splice(0).forEach((app) => app.unmount());
	document.body.innerHTML = "";
});

beforeEach(() => {
	resetListedViews();
	fetchViews.mockReset();
	viewsSidebarDrawn.value = null;
});

async function sidebar(path: string): Promise<{ host: HTMLElement; router: Router; app: ReturnType<typeof createApp> }> {
	const boot = {
		app: "frappe",
		shell_base: "/apps/frappe",
		prefixes: { frappe: { app: "frappe", modular: false } },
		session: { user: { name: "a@example.com" }, roles: [] },
		view_types: [
			{ name: "List", icon: "list" },
			{ name: "Cards", icon: "layout-grid" },
		],
		unbuilt_view_types: [{ name: "Kanban", label: "Kanban", icon: "kanban" }],
	} as unknown as Boot;
	const router = createRouter({
		history: createMemoryHistory(),
		routes: [
			{ path: "/:doctype", name: "list", component: stub },
			{ path: "/:doctype/view/:key", name: "saved-view", component: stub },
		],
	});
	registerShell({ boot, addresses, router });
	await router.push(path);
	const host = document.body.appendChild(document.createElement("div"));
	const app = createApp({ render: () => h(ViewsSidebar, { doctype: "ToDo", title: "ToDo" }) });
	app.provide("boot", boot);
	app.provide("addresses", addresses);
	app.config.globalProperties.__ = (text: string, args?: unknown[] | null) => text.replace(/\{(\d+)\}/g, (_, i) => String(args?.[Number(i)]));
	app.use(router);
	app.mount(host);
	mounted.push(app);
	await new Promise((done) => setTimeout(done, 0));
	await nextTick();
	return { host, router, app };
}

const rows = (host: HTMLElement) => [...host.querySelectorAll("[data-key]")].map((row) => row.getAttribute("data-key"));
const headings = (host: HTMLElement) => [...host.querySelectorAll("p")].map((one) => one.textContent?.trim());

describe("the views sidebar body", () => {
	it("lists the views by group, then the unbuilt types as Soon rows", async () => {
		fetchViews.mockResolvedValue(VIEWS);
		const { host } = await sidebar("/todo");
		expect(rows(host)).toEqual(["list", "cards", "kanban", "mine", "team"]);
		expect(headings(host)).toEqual(expect.arrayContaining(["My views", "Site views"]));
		expect(host.querySelector('[data-key="kanban"]')!.textContent).toContain("Soon");
	});

	it("marks the open view, and the plain list at /<doctype>", async () => {
		fetchViews.mockResolvedValue(VIEWS);
		const { host, router } = await sidebar("/todo");
		const current = () => [...host.querySelectorAll("[aria-current='page']")].map((a) => a.closest("[data-key]")?.getAttribute("data-key"));
		expect(current()).toEqual(["list"]);
		await router.push("/todo/view/mine");
		await nextTick();
		expect(current()).toEqual(["mine"]);
	});

	it("puts the house on the default view only, with a lane on every real row", async () => {
		fetchViews.mockResolvedValue(VIEWS);
		const { host } = await sidebar("/todo");
		const marked = [...host.querySelectorAll("[data-view-mark='default']")].map((one) => one.closest("[data-key]")?.getAttribute("data-key"));
		expect(marked).toEqual(["list"]);
		expect(host.querySelectorAll("[data-view-lane]")).toHaveLength(4);
	});

	it("shows the dot where the open list says its view has changes, in place of the house", async () => {
		fetchViews.mockResolvedValue(VIEWS);
		const scope = effectScope();
		scope.run(() => markModifiedView({ doctype: "ToDo", key: "mine", layer: "own", modified: ref(true) } as unknown as View));
		const { host } = await sidebar("/todo/view/mine");
		const dotted = [...host.querySelectorAll("[data-view-mark='modified']")].map((one) => one.closest("[data-key]")?.getAttribute("data-key"));
		expect(dotted).toEqual(["mine"]);
		expect(host.querySelector("[data-view-mark='modified'][aria-label='Unsaved changes']")).not.toBeNull();
		// The house stays on the default, which has no changes.
		expect(host.querySelector("[data-view-mark='default']")!.closest("[data-key]")?.getAttribute("data-key")).toBe("list");
		scope.stop();
	});
});

describe("what the rows say to assistive tech and to the next visit", () => {
	it("names a Soon row with its status, not the two words run together", async () => {
		fetchViews.mockResolvedValue(VIEWS);
		const { host } = await sidebar("/todo");
		expect(host.querySelector('[data-key="kanban"] [aria-label]')!.getAttribute("aria-label")).toBe("Kanban, soon");
	});

	it("names each row's ⋯ after its view", async () => {
		fetchViews.mockResolvedValue(VIEWS);
		const { host } = await sidebar("/todo");
		const names = [...host.querySelectorAll("button[data-view-menu]")].map((one) => one.getAttribute("aria-label"));
		expect(names).toContain("Options for Mine");
	});

	it("arms the default-skip on a plain click of List, not on a modified one", async () => {
		fetchViews.mockResolvedValue(VIEWS);
		const { host } = await sidebar("/todo/view/mine");
		const link = host.querySelector('[data-key="list"] a')! as HTMLElement;
		link.addEventListener("click", (event) => event.preventDefault());
		link.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, ctrlKey: true }));
		expect(consumeSkip("ToDo")).toBe(false);
		link.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
		expect(consumeSkip("ToDo")).toBe(true);
	});
});

describe("telling the crumb the rows are drawn", () => {
	it("holds back until the views have arrived", async () => {
		let answer!: (views: ListedView[]) => void;
		fetchViews.mockReturnValue(new Promise((done) => (answer = done)));
		const { host } = await sidebar("/todo");
		expect(viewsSidebarDrawn.value).toBeNull();
		expect(rows(host)).toEqual([]);
		answer(VIEWS);
		await new Promise((done) => setTimeout(done, 0));
		expect(viewsSidebarDrawn.value).toBe("ToDo");
	});

	it("stays off when the read fails, so the crumb keeps its list of views", async () => {
		fetchViews.mockRejectedValue(new Error("offline"));
		await sidebar("/todo");
		expect(viewsSidebarDrawn.value).toBeNull();
	});

	it("clears when the sidebar goes away", async () => {
		fetchViews.mockResolvedValue(VIEWS);
		const { app } = await sidebar("/todo");
		expect(viewsSidebarDrawn.value).toBe("ToDo");
		app.unmount();
		mounted.splice(0);
		expect(viewsSidebarDrawn.value).toBeNull();
	});
});
