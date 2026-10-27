// The page states: which one a failed read shows, how each draws, and the frame drawing one in place of the content.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick, type Component } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";
import { ApiError, getTranslations } from "@framework/ui/api";
import { loadTranslations } from "@/i18n";

import PageFrame from "../PageFrame.vue";
import PageState from "../PageState.vue";
import { failedState, type PageStateName } from "../pageState";

vi.mock("@framework/ui/api", async (original) => ({
	...(await original<typeof import("@framework/ui/api")>()),
	getTranslations: vi.fn(),
}));

const mounted: ReturnType<typeof createApp>[] = [];

afterEach(() => {
	for (const app of mounted.splice(0)) app.unmount();
	document.body.innerHTML = "";
	vi.restoreAllMocks();
});

const crm = { app: "crm", app_title: "CRM" };
const BASE = "/apps/crm";

async function mount(render: () => ReturnType<typeof h>, { at = "/crm-lead/x" } = {}) {
	const router = createRouter({
		history: createMemoryHistory(BASE),
		routes: [
			{ path: "/", name: "home", component: { render: () => null } },
			{ path: "/:pathMatch(.*)*", component: { render: () => null } },
		],
	});
	await router.push(at);
	const root = document.createElement("div");
	document.body.appendChild(root);
	const app = createApp({ render });
	app.use(router).provide("boot", crm);
	app.mount(root);
	mounted.push(app);
	return root;
}

function action(root: HTMLElement) {
	return root.querySelector<HTMLAnchorElement>("[data-page-state] a");
}

function tryAgain(root: HTMLElement) {
	return [...root.querySelectorAll("button")].find(
		(button) => button.textContent?.trim() === "Try again"
	);
}

const retry = () => {};

describe("failedState", () => {
	it("is offline when the request never reached the server", () => {
		const failure = new ApiError({ type: "NetworkError", message: "TypeError: Failed to fetch" }, 0);
		expect(failedState(failure, retry)).toEqual({ name: "offline", retry });
	});

	it("is offline when the browser is, whatever the error", () => {
		vi.spyOn(navigator, "onLine", "get").mockReturnValue(false);
		expect(failedState(new TypeError("Failed to fetch dynamically imported module"), retry).name).toBe(
			"offline"
		);
	});

	it("is not offline when the server answered, whatever the browser says", () => {
		vi.spyOn(navigator, "onLine", "get").mockReturnValue(false);
		const refused = new ApiError({ type: "PermissionError", message: "No" }, 403);
		expect(failedState(refused, retry).name).toBe("noPermission");
	});

	it("is no permission on a 403 and not found on a 404, with no retry", () => {
		const refused = new ApiError({ type: "PermissionError", message: "No" }, 403);
		const missing = new ApiError({ type: "DoesNotExistError", message: "Gone" }, 404);
		expect(failedState(refused, retry)).toEqual({ name: "noPermission" });
		expect(failedState(missing, retry)).toEqual({ name: "notFound" });
	});

	it("is failed with the server's message as text", () => {
		const failure = new ApiError({ type: "ValidationError", message: "<p>Row <b>3</b>:<br>bad</p>" }, 417);
		expect(failedState(failure, retry)).toEqual({ name: "failed", message: "Row 3:\nbad", retry });
	});

	it("is failed with no message for an error the request wrapper made, or a browser error", () => {
		const status = new ApiError({ type: "HTTPError", message: "GET /x failed with status 502" }, 502);
		expect(failedState(status, retry).message).toBeUndefined();
		expect(failedState(new TypeError("x is undefined"), retry).message).toBeUndefined();
	});
});

describe("PageState", () => {
	it.each<[PageStateName, string]>([
		["empty", "Nothing here yet"],
		["filtered", "No matching records"],
		["notFound", "Not found"],
		["noPermission", "No permission"],
		["offline", "No connection"],
		["failed", "Something went wrong"],
	])("draws the %s state with its own words", async (name, title) => {
		const root = await mount(() => h(PageState, { name }));
		expect(root.querySelector(`[data-page-state="${name}"]`)?.textContent).toContain(title);
	});

	it("says the person may not see this when no permission names no act", async () => {
		const root = await mount(() => h(PageState, { name: "noPermission" }));
		expect(root.textContent).toContain("You do not have permission to see this.");
	});

	it("names the denied act in gray words, never in the red message", async () => {
		const act = { name: "create", doctype: "Note" } as const;
		const root = await mount(() => h(PageState, { name: "noPermission", act }));
		const words = [...root.querySelectorAll("p")].find(
			(p) => p.textContent === "You do not have permission to create Note.",
		);
		expect(words?.classList.contains("text-ink-gray-6")).toBe(true);
		expect(root.textContent).not.toContain("You do not have permission to see this.");
		expect(root.querySelector(".text-ink-red-7")).toBeNull();
	});

	it("names the doctype by its translated label", async () => {
		const permission = "You do not have permission to create {0}.";
		const german = { Note: "Notiz", [permission]: "Kein Recht, {0} anzulegen." };
		vi.mocked(getTranslations).mockResolvedValue({ data: german });
		await loadTranslations("v1", "de");
		try {
			const act = { name: "create", doctype: "Note" } as const;
			const root = await mount(() => h(PageState, { name: "noPermission", act }));
			expect(root.textContent).toContain("Kein Recht, Notiz anzulegen.");
		} finally {
			vi.mocked(getTranslations).mockResolvedValue({ data: {} });
			await loadTranslations("v2", "en");
		}
	});

	it("announces a refusal or failure, and not an empty list", async () => {
		const failed = await mount(() => h(PageState, { name: "failed" }));
		const empty = await mount(() => h(PageState, { name: "empty" }));
		expect(failed.querySelector("[role='alert']")).not.toBeNull();
		expect(empty.querySelector("[role='alert']")).toBeNull();
	});

	it("draws an escaped tag in the server's message as text, never as markup", async () => {
		const failure = new ApiError({ type: "ValidationError", message: "Bad name &lt;img src=x&gt;" }, 417);
		const root = await mount(() => h(PageState, failedState(failure, retry)));
		expect(root.querySelector("img")).toBeNull();
		expect(root.textContent).toContain("Bad name <img src=x>");
	});

	it("draws the server's message under its own words", async () => {
		const root = await mount(() => h(PageState, { name: "failed", message: "Disk is full" }));
		expect(root.textContent).toContain("This page could not load.Disk is full");
	});

	it("holds Try again busy until the retry settles", async () => {
		let settle!: () => void;
		const pending = new Promise<void>((resolve) => (settle = resolve));
		const root = await mount(() => h(PageState, { name: "failed", retry: () => pending }));

		tryAgain(root)!.click();
		await nextTick();
		expect(tryAgain(root)!.disabled).toBe(true);

		settle();
		await pending;
		await nextTick();
		expect(tryAgain(root)!.disabled).toBe(false);
	});

	it("offers no Try again without a retry", async () => {
		const root = await mount(() => h(PageState, { name: "notFound" }));
		expect(tryAgain(root)).toBeUndefined();
	});

	it("offers the app's home when not found, labelled with the app's title", async () => {
		const root = await mount(() => h(PageState, { name: "notFound" }));
		expect(action(root)?.textContent?.trim()).toBe("Go to CRM home");
		expect(action(root)?.getAttribute("href")).toBe(`${BASE}/`);
	});

	it("offers no home on the home page itself, nor on any other state", async () => {
		const home = await mount(() => h(PageState, { name: "notFound" }), { at: "/" });
		expect(action(home)).toBeNull();
		for (const name of ["empty", "filtered", "noPermission", "offline", "failed"] as const) {
			const root = await mount(() => h(PageState, { name }));
			expect(action(root)).toBeNull();
		}
	});
});

describe("PageFrame's state", () => {
	function frame(props: Record<string, unknown>) {
		return mount(() => h(PageFrame as Component, props, { default: () => h("p", { "data-content": "" }) }));
	}

	it("takes the content's place, in a frame that scrolls or not", async () => {
		for (const scroll of [true, false]) {
			const root = await frame({ scroll, state: { name: "noPermission" } });
			expect(root.querySelector('[data-page-state="noPermission"]')).not.toBeNull();
			expect(root.querySelector("[data-content]")).toBeNull();
		}
	});

	it("leaves the content alone when there is none", async () => {
		const root = await frame({ state: null });
		expect(root.querySelector("[data-page-state]")).toBeNull();
		expect(root.querySelector("[data-content]")).not.toBeNull();
	});
});
