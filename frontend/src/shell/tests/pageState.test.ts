// The page states: which one a failed read shows, how each draws, and the frame drawing one in place of the content.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick, type Component } from "vue";
import { ApiError } from "@framework/ui/api";

import PageFrame from "../PageFrame.vue";
import PageState from "../PageState.vue";
import { failedState, type PageStateName } from "../pageState";

const mounted: ReturnType<typeof createApp>[] = [];

afterEach(() => {
	for (const app of mounted.splice(0)) app.unmount();
	document.body.innerHTML = "";
	vi.restoreAllMocks();
});

function mount(render: () => ReturnType<typeof h>) {
	const root = document.createElement("div");
	document.body.appendChild(root);
	const app = createApp({ render });
	app.mount(root);
	mounted.push(app);
	return root;
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
	])("draws the %s state with its own words", (name, title) => {
		const root = mount(() => h(PageState, { name }));
		expect(root.querySelector(`[data-page-state="${name}"]`)?.textContent).toContain(title);
	});

	it("announces a refusal or failure, and not an empty list", () => {
		const failed = mount(() => h(PageState, { name: "failed" }));
		const empty = mount(() => h(PageState, { name: "empty" }));
		expect(failed.querySelector("[role='alert']")).not.toBeNull();
		expect(empty.querySelector("[role='alert']")).toBeNull();
	});

	it("draws an escaped tag in the server's message as text, never as markup", () => {
		const failure = new ApiError({ type: "ValidationError", message: "Bad name &lt;img src=x&gt;" }, 417);
		const root = mount(() => h(PageState, failedState(failure, retry)));
		expect(root.querySelector("img")).toBeNull();
		expect(root.textContent).toContain("Bad name <img src=x>");
	});

	it("draws the server's message under its own words", () => {
		const root = mount(() => h(PageState, { name: "failed", message: "Disk is full" }));
		expect(root.textContent).toContain("This page could not load.Disk is full");
	});

	it("holds Try again busy until the retry settles", async () => {
		let settle!: () => void;
		const pending = new Promise<void>((resolve) => (settle = resolve));
		const root = mount(() => h(PageState, { name: "failed", retry: () => pending }));

		tryAgain(root)!.click();
		await nextTick();
		expect(tryAgain(root)!.disabled).toBe(true);

		settle();
		await pending;
		await nextTick();
		expect(tryAgain(root)!.disabled).toBe(false);
	});

	it("offers no Try again without a retry", () => {
		const root = mount(() => h(PageState, { name: "notFound" }));
		expect(tryAgain(root)).toBeUndefined();
	});
});

describe("PageFrame's state", () => {
	function frame(props: Record<string, unknown>) {
		return mount(() => h(PageFrame as Component, props, { default: () => h("p", { "data-content": "" }) }));
	}

	it("takes the content's place, in a frame that scrolls or not", () => {
		for (const scroll of [true, false]) {
			const root = frame({ scroll, state: { name: "noPermission" } });
			expect(root.querySelector('[data-page-state="noPermission"]')).not.toBeNull();
			expect(root.querySelector("[data-content]")).toBeNull();
		}
	});

	it("leaves the content alone when there is none", () => {
		const root = frame({ state: null });
		expect(root.querySelector("[data-page-state]")).toBeNull();
		expect(root.querySelector("[data-content]")).not.toBeNull();
	});
});
