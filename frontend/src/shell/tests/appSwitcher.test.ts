// The quick app switcher: the order it lists, and the key flow from Alt+` to the app it opens.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, type App } from "vue";

const fake = vi.hoisted(() => ({ apps: [] as unknown[], loadDocument: vi.fn() }));

vi.mock("../palettePlaces", () => ({ loadApps: async () => fake.apps }));
vi.mock("../tabKeepAlive", () => ({ loadDocument: fake.loadDocument }));

import type { Boot } from "@/boot";
import { installTranslate } from "@/i18n";
import { appSwitcher } from "../appSwitcher";
import { AppSwitcherKey } from "../appSwitcherKey";
import { switchOrder, menuApps } from "../appSwitchOrder";
import { appsUsed, recordAppUse } from "../appUse";
import type { PlacesApp } from "../palettePlaces";

const app = (name: string, extra: Partial<PlacesApp> = {}): PlacesApp => ({
	app: name,
	title: name,
	route: `/apps/${name}`,
	kind: "prefix",
	hidden: false,
	...extra,
});
const boot = (current: string | null) =>
	({ app: current, session: { user: { name: "jane@example.com" } } }) as unknown as Boot;

beforeEach(() => localStorage.clear());

describe("the order", () => {
	const apps = [app("books"), app("crm"), app("hrms"), app("wiki")];

	it("puts the current app first, then the last opened, then the rest as /apps has them", () => {
		expect(switchOrder(apps, "wiki", ["hrms", "wiki", "crm"]).map((one) => one.app)).toEqual([
			"wiki",
			"hrms",
			"crm",
			"books",
		]);
	});

	it("leaves hidden apps out, and a link tile in", () => {
		const listed = switchOrder([app("books", { hidden: true }), app("old", { kind: "link", route: "/desk" })], null, []);
		expect(listed.map((one) => one.app)).toEqual(["old"]);
	});

	it("remembers the apps opened, newest first, once each", () => {
		recordAppUse(boot("crm"));
		recordAppUse(boot("books"));
		recordAppUse(boot("crm"));
		recordAppUse(boot(null));
		expect(appsUsed(boot("crm"))).toEqual(["crm", "books"]);
	});

	it("lists the menu's apps in /apps order, less the current and the hidden", () => {
		const listed = menuApps([...apps.slice(0, 2), app("old", { hidden: true }), apps[3]], "crm");
		expect(listed.map((one) => one.app)).toEqual(["books", "wiki"]);
	});
});

describe("the keys", () => {
	const mounted: App[] = [];
	const press = (init: KeyboardEventInit, target: EventTarget = document.body) =>
		target.dispatchEvent(new KeyboardEvent("keydown", { bubbles: true, cancelable: true, ...init }));
	const tick = async (init: KeyboardEventInit = {}, target?: EventTarget) => {
		const event = press({ code: "Backquote", key: "`", altKey: true, ...init }, target);
		await vi.waitFor(() => expect(appSwitcher.open.value || appSwitcher.engaged === false).toBe(true));
		return event;
	};
	const letGo = () => document.dispatchEvent(new KeyboardEvent("keyup", { key: "Alt", bubbles: true, cancelable: true }));
	const selected = () => appSwitcher.apps.value[appSwitcher.selected.value]?.app;

	function mountKeys(current: string | null) {
		const root = createApp(defineComponent({ render: () => [h("input", { name: "field" }), h(AppSwitcherKey)] }));
		installTranslate(root);
		root.provide("boot", boot(current));
		root.mount(document.body.appendChild(document.createElement("div")));
		mounted.push(root);
	}

	beforeEach(() => {
		fake.apps = [app("books"), app("crm"), app("hrms"), app("old", { kind: "link", route: "/desk" })];
		fake.loadDocument.mockClear();
		localStorage.setItem("frappe:desk:app-use", JSON.stringify({ "jane@example.com": ["crm", "hrms", "books"] }));
		mountKeys("crm");
	});

	afterEach(() => {
		appSwitcher.cancel();
		for (const root of mounted.splice(0)) root.unmount();
		document.body.innerHTML = "";
	});

	it("opens on the previous app, and a tap and release goes straight to it", async () => {
		await tick();
		expect(selected()).toBe("hrms");
		letGo();
		expect(appSwitcher.open.value).toBe(false);
		expect(fake.loadDocument).toHaveBeenCalledWith("/apps/hrms");
	});

	it("moves on with each tap, and Shift goes back", async () => {
		await tick();
		await tick();
		expect(selected()).toBe("books");
		await tick();
		expect(selected()).toBe("old");
		await tick({ shiftKey: true });
		expect(selected()).toBe("books");
		letGo();
		expect(fake.loadDocument).toHaveBeenCalledWith("/apps/books");
	});

	it("moves with the arrows and opens on Enter, with the link tile's own route", async () => {
		await tick();
		press({ key: "ArrowRight", altKey: true });
		press({ key: "ArrowRight", altKey: true });
		press({ key: "ArrowRight", altKey: true });
		expect(selected()).toBe("crm");
		press({ key: "ArrowLeft", altKey: true });
		expect(selected()).toBe("old");
		press({ key: "Enter", altKey: true });
		expect(fake.loadDocument).toHaveBeenCalledWith("/desk");
	});

	it("opens nothing on Esc", async () => {
		await tick();
		press({ key: "Escape", altKey: true });
		letGo();
		expect(appSwitcher.open.value).toBe(false);
		expect(fake.loadDocument).not.toHaveBeenCalled();
	});

	it("is a modal dialog that takes focus, follows the selection, and gives focus back", async () => {
		const input = document.querySelector("input")!;
		input.focus();
		await tick({}, input);
		const list = await vi.waitFor(() => document.querySelector<HTMLElement>("[role=listbox]")!);
		expect(list.closest("[role=dialog]")?.getAttribute("aria-modal")).toBe("true");
		await vi.waitFor(() => expect(document.activeElement).toBe(list));
		const active = () => document.getElementById(list.getAttribute("aria-activedescendant")!);
		expect(active()?.dataset.app).toBe("hrms");
		press({ key: "ArrowRight", altKey: true });
		await nextTick();
		expect(active()?.dataset.app).toBe("books");
		press({ key: "Escape", altKey: true });
		await nextTick();
		expect(document.activeElement).toBe(input);
	});

	it("opens from a focused text input, which it types nothing into", async () => {
		const input = document.querySelector("input")!;
		input.focus();
		const event = await tick({}, input);
		expect(event).toBe(false);
		expect(appSwitcher.open.value).toBe(true);
	});

	it("ignores a held key's repeats", async () => {
		await tick();
		press({ code: "Backquote", key: "`", altKey: true, repeat: true });
		await nextTick();
		expect(selected()).toBe("hrms");
	});

	it("closes when the window loses focus, or when a key comes with Alt up", async () => {
		await tick();
		window.dispatchEvent(new Event("blur"));
		expect(appSwitcher.open.value).toBe(false);
		await tick();
		press({ code: "KeyA", key: "a", altKey: false });
		expect(appSwitcher.open.value).toBe(false);
		expect(fake.loadDocument).toHaveBeenCalledWith("/apps/hrms");
	});

	it("selects the most recent app on /apps, and the last one with Shift", async () => {
		for (const root of mounted.splice(0)) root.unmount();
		mountKeys(null);
		await tick();
		expect(selected()).toBe("crm");
		appSwitcher.cancel();
		await tick({ shiftKey: true });
		expect(selected()).toBe("old");
	});

	it("opens nothing when the current app is the only one", async () => {
		appSwitcher.cancel();
		fake.apps = [app("crm")];
		press({ code: "Backquote", key: "`", altKey: true });
		await nextTick();
		await nextTick();
		expect(appSwitcher.open.value).toBe(false);
	});
});
