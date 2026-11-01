// A standing window: what an app's shell hook attaches with `shell.window`, drawn by the shell's row.
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, onUnmounted, type Component } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";

vi.mock("@framework/ui/api", async (importOriginal) => ({
	...(await importOriginal<typeof import("@framework/ui/api")>()),
	getTranslations: vi.fn(),
	getMeta: vi.fn(async () => ({ data: null, children: [] })),
}));

vi.mock("@/arrangement", async (importOriginal) => ({
	...(await importOriginal<typeof import("@/arrangement")>()),
	fetchArrangement: vi.fn().mockResolvedValue([]),
}));

import { Addresses } from "@/addresses";
import type { Boot, ShellHook } from "@/boot";
import { registerContributions, shellHookFiles } from "@/contributions/registry";
import { installTranslate } from "@/i18n";
import { resetSprite } from "@/icons/sprite";
import { resetNavigationReports } from "@/navigation/registry";
import { registerShell } from "@/router/routeFor";
import AppShell from "../AppShell.vue";
import { registerComposerBand, registerFloatingComposer } from "../composer";
import type { ShellHookApi } from "../shellHooks";
import type { StandingWindowHandle, StandingWindowOptions } from "../standingWindows";

const addresses = new Addresses({ doctypes: {}, modules: {} });

const boot = {
	app: "crm",
	app_title: "CRM",
	shell_base: "/apps/crm",
	prefixes: { crm: { app: "crm", modular: false } },
	navigation: { rail: [], sidebars: {} },
	session: { user: { name: "sales@example.com", full_name: "Sales", email: "sales@example.com" } },
} as unknown as Boot;

const CRM = { app: "crm", title: "CRM" };
const HELPDESK = { app: "helpdesk", title: "Helpdesk" };

const releases: (() => void)[] = [];
let frames: FrameRequestCallback[] = [];

async function flush() {
	for (let turn = 0; turn < 3; turn++) {
		await new Promise((resolve) => setTimeout(resolve, 0));
		await nextTick();
	}
}

/** Mounts the shell for `hooks`, then lets the first paint and the idle time after it pass. */
async function mount(hooks: ShellHook[] = [CRM]) {
	const booted = { ...boot, shell_hooks: hooks } as Boot;
	const router = createRouter({
		history: createMemoryHistory(booted.shell_base),
		routes: [{ path: "/", name: "home", component: { render: () => null } }],
	});
	registerShell({ boot: booted, addresses, router });
	const app = createApp(AppShell);
	installTranslate(app);
	app.provide("boot", booted);
	app.provide("addresses", addresses);
	app.use(router);
	await router.push("/");
	await router.isReady();
	app.mount(document.body.appendChild(document.createElement("div")));
	releases.push(() => app.unmount());
	await flush();
	frames.splice(0).forEach((frame) => frame(performance.now()));
	await flush();
}

/** Ships a shell.js for `app` whose setup calls `attach` with the hook's `shell`. */
function ship(app: string, attach: (shell: ShellHookApi) => unknown) {
	shellHookFiles.push({ app, load: async () => ({ setup: attach }) });
}

/** Ships `app` with one window of `component`, and gives back its handle once the hook ran. */
async function attached(
	component: Component = Body,
	options: StandingWindowOptions = { icon: "lucide-phone", width: 280 }
) {
	let handle: StandingWindowHandle | undefined;
	ship("crm", (shell) => (handle = shell.window(component, options)));
	await mount();
	return handle!;
}

const mounts = vi.fn();
const unmounts = vi.fn();
const given = vi.fn();

const Body = defineComponent({
	props: { shell: Object, window: Object },
	setup(props) {
		mounts();
		given(props);
		onUnmounted(unmounts);
		return () => h("input", { "data-call-note": "" });
	},
});

const frame = (app = "crm") =>
	document.querySelector<HTMLElement>(`[data-standing-window="${app}"]`)!;
const pill = (app = "crm") =>
	document.querySelector<HTMLElement>(`[data-standing-minimised="${app}"]`)!;
const shown = (element: HTMLElement) => element.closest<HTMLElement>("[style*='display: none']") === null;
const header = () => frame().querySelector<HTMLElement>("[data-standing-title]")!.parentElement!;
const live = () => document.querySelector<HTMLElement>("[aria-live='polite']")!;

beforeAll(() => registerContributions(["frappe"]));

beforeEach(() => {
	shellHookFiles.length = 0;
	frames = [];
	vi.spyOn(window, "requestAnimationFrame").mockImplementation((frame) => frames.push(frame));
	vi.spyOn(console, "warn").mockImplementation(() => {});
	vi.spyOn(console, "error").mockImplementation(() => {});
	localStorage.clear();
	resetNavigationReports();
	resetSprite();
	mounts.mockClear();
	unmounts.mockClear();
	given.mockClear();
});

afterEach(() => {
	releases.splice(0).forEach((release) => release());
	document.body.innerHTML = "";
	shellHookFiles.length = 0;
	vi.restoreAllMocks();
});

describe("shell.window", () => {
	it("mounts the component at once, closed, with the act Shell and the handle", async () => {
		const handle = await attached();

		expect(mounts).toHaveBeenCalledOnce();
		expect(handle.state).toBe("closed");
		expect(shown(frame())).toBe(false);
		expect(shown(pill())).toBe(false);
		const props = given.mock.calls[0][0];
		expect(props.window).toBe(handle);
		expect(Object.keys(props.shell)).toEqual(
			expect.arrayContaining(["router", "toast", "call", "run", "create", "dialog"])
		);
	});

	it("shows the frame while open and the pill while minimised, and never remounts", async () => {
		const handle = await attached();

		handle.open();
		await nextTick();
		expect(handle.state).toBe("open");
		expect(shown(frame())).toBe(true);
		expect(shown(pill())).toBe(false);
		expect(frame().getAttribute("role")).toBe("dialog");
		expect(frame().getAttribute("aria-modal")).toBe("false");

		handle.minimise();
		await nextTick();
		expect(handle.state).toBe("minimised");
		expect(shown(frame())).toBe(false);
		expect(shown(pill())).toBe(true);

		handle.close();
		await nextTick();
		expect(handle.state).toBe("closed");
		expect(shown(frame())).toBe(false);
		expect(shown(pill())).toBe(false);

		expect(mounts).toHaveBeenCalledOnce();
		expect(unmounts).not.toHaveBeenCalled();
	});

	it("is minimised and closed from the frame's own buttons, and restored by a click on the pill", async () => {
		const handle = await attached();
		handle.open();
		await nextTick();

		frame().querySelector<HTMLElement>("[data-standing-minimise]")!.click();
		await nextTick();
		expect(handle.state).toBe("minimised");

		pill().click();
		await nextTick();
		expect(handle.state).toBe("open");

		frame().querySelector<HTMLElement>("[data-standing-close]")!.click();
		await nextTick();
		expect(handle.state).toBe("closed");
		expect(unmounts).not.toHaveBeenCalled();
	});

	it("is titled by the app until the app sets a title, and announces it politely while open", async () => {
		const handle = await attached();
		handle.open();
		await nextTick();
		expect(header().textContent).toContain("CRM");
		expect(live().textContent).toBe("CRM");

		handle.setTitle("Call · Emma Williams");
		await nextTick();
		expect(frame().querySelector("[data-standing-title]")!.textContent!.trim()).toBe(
			"Call · Emma Williams"
		);
		expect(frame().getAttribute("aria-labelledby")).toBe(
			frame().querySelector("[data-standing-title]")!.id
		);
		expect(live().textContent).toBe("Call · Emma Williams");

		handle.minimise();
		await nextTick();
		expect(pill().textContent).toContain("Call · Emma Williams");
		expect(live().textContent).toBe("");
	});

	it("draws its actions in the frame and the pill, and an action's click does not restore", async () => {
		const handle = await attached();
		const hangUp = vi.fn();
		handle.setActions([
			{ label: "Mute", icon: "lucide-mic-off", run: vi.fn() },
			{ label: "Hang up", icon: "lucide-phone-off", theme: "red", run: hangUp },
		]);
		handle.open();
		await nextTick();

		const labels = (root: HTMLElement) =>
			[...root.querySelectorAll("[data-standing-action]")].map((button) =>
				button.getAttribute("aria-label")
			);
		expect(labels(frame())).toEqual(["Mute", "Hang up"]);
		frame().querySelectorAll<HTMLElement>("[data-standing-action]")[1].click();
		expect(hangUp).toHaveBeenCalledOnce();

		handle.minimise();
		await nextTick();
		expect(labels(pill())).toEqual(["Mute", "Hang up"]);
		pill().querySelectorAll<HTMLElement>("[data-standing-action]")[1].click();
		await nextTick();
		expect(hangUp).toHaveBeenCalledTimes(2);
		expect(handle.state).toBe("minimised");
	});

	it("draws at most three actions and warns about the rest", async () => {
		const handle = await attached();
		const action = (label: string) => ({ label, icon: "lucide-circle", run: vi.fn() });
		handle.setActions(["One", "Two", "Three", "Four"].map(action));
		handle.open();
		await nextTick();

		expect(frame().querySelectorAll("[data-standing-action]")).toHaveLength(3);
		expect(vi.mocked(console.warn)).toHaveBeenCalledWith(
			"[frappe] crm's window draws only its first three actions."
		);
	});

	it("logs an action that fails", async () => {
		const handle = await attached();
		handle.setActions([
			{ label: "Hang up", icon: "lucide-phone-off", run: () => Promise.reject(new Error("gone")) },
		]);
		handle.open();
		await nextTick();

		frame().querySelector<HTMLElement>("[data-standing-action]")!.click();
		await flush();

		expect(vi.mocked(console.error).mock.calls.map(([message]) => message)).toContain(
			'[frappe] crm\'s window action "Hang up" failed.'
		);
	});

	it("offers close until the app makes it not closable", async () => {
		const handle = await attached();
		handle.open();
		await nextTick();
		expect(frame().querySelector("[data-standing-close]")).not.toBeNull();

		handle.setClosable(false);
		await nextTick();
		expect(frame().querySelector("[data-standing-close]")).toBeNull();
		expect(frame().querySelector("[data-standing-minimise]")).not.toBeNull();

		handle.setClosable(true);
		await nextTick();
		expect(frame().querySelector("[data-standing-close]")).not.toBeNull();
	});

	it.each([
		[100, "240px"],
		[320, "320px"],
		[900, "400px"],
		[undefined, "280px"],
	])("clamps a width of %s to %s", async (width, drawn) => {
		await attached(Body, { icon: "lucide-phone", width });
		expect(frame().style.width).toBe(drawn);
	});

	it("drops the divider below 280px wide", async () => {
		const action = { label: "Mute", icon: "lucide-mic-off", run: vi.fn() };
		const handle = await attached(Body, { width: 240 });
		handle.setActions([action]);
		await nextTick();
		expect(frame().querySelector("[data-standing-divider]")).toBeNull();

		releases.splice(0).forEach((release) => release());
		shellHookFiles.length = 0;
		const wide = await attached(Body, { width: 280 });
		wide.setActions([action]);
		await nextTick();
		expect(frame().querySelector("[data-standing-divider]")).not.toBeNull();
	});

	it("never moves focus when opened, and Esc in it does not minimise", async () => {
		const handle = await attached();
		const field = document.body.appendChild(document.createElement("input"));
		field.focus();

		handle.open();
		await nextTick();
		expect(document.activeElement).toBe(field);

		const note = frame().querySelector<HTMLInputElement>("[data-call-note]")!;
		note.focus();
		note.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
		await nextTick();
		expect(handle.state).toBe("open");
		expect(document.activeElement).toBe(note);
	});

	it("warns at a second call from the same app and ignores it", async () => {
		const handles: unknown[] = [];
		ship("crm", (shell) => {
			handles.push(shell.window(Body, { icon: "lucide-phone" }));
			handles.push(shell.window(Body, { icon: "lucide-timer" }));
		});
		await mount();

		expect(handles[1]).toBeUndefined();
		expect(mounts).toHaveBeenCalledOnce();
		expect(document.querySelectorAll("[data-standing-window]")).toHaveLength(1);
		expect(vi.mocked(console.warn)).toHaveBeenCalledWith(
			"[frappe] crm's shell.js asked for a second window; it is ignored."
		);
	});

	it("draws two apps' windows in app order, whichever attaches first", async () => {
		let attachCrm = () => {};
		const handles: Record<string, StandingWindowHandle | undefined> = {};
		ship("crm", (shell) => {
			attachCrm = () => (handles.crm = shell.window(Body));
		});
		ship("helpdesk", (shell) => (handles.helpdesk = shell.window(Body)));
		await mount([CRM, HELPDESK]);
		attachCrm();
		await nextTick();
		handles.crm!.open();
		handles.helpdesk!.minimise();
		await nextTick();

		const row = document.querySelector("[data-standing-row]")!;
		const order = [...row.querySelectorAll("[data-standing-window]")].map((element) =>
			element.getAttribute("data-standing-window")
		);
		expect(order).toEqual(["crm", "helpdesk"]);
		expect(shown(frame("crm"))).toBe(true);
		expect(shown(pill("helpdesk"))).toBe(true);
		expect(pill("helpdesk").textContent).toContain("Helpdesk");
	});
});

describe("the row", () => {
	// A browser's observer reports an element once as it starts observing it; happy-dom's never does.
	class ReportingResizeObserver {
		constructor(private report: ResizeObserverCallback) {}
		observe(target: Element) {
			this.report([{ target } as ResizeObserverEntry], this as unknown as ResizeObserver);
		}
		unobserve() {}
		disconnect() {}
	}

	beforeEach(() => vi.stubGlobal("ResizeObserver", ReportingResizeObserver));
	afterEach(() => vi.unstubAllGlobals());

	const row = () => document.querySelector<HTMLElement>("[data-standing-row]")!;
	const at = (rect: Partial<DOMRect>) => {
		const element = document.body.appendChild(document.createElement("div"));
		element.getBoundingClientRect = () => ({ left: 0, top: 0, width: 0, height: 0, ...rect }) as DOMRect;
		return element;
	};

	it("sits on the shell's 24px bottom line at the right", async () => {
		await attached();
		expect(row().style.right).toBe("24px");
		expect(row().style.bottom).toBe("24px");
	});

	it("sits 12px left of a floating composer, on the same bottom line", async () => {
		await attached();
		const release = registerFloatingComposer(at({ left: innerWidth - 484, top: 100 }));
		await flush();
		expect(row().style.right).toBe("496px");
		expect(row().style.bottom).toBe("24px");

		release();
		await flush();
		expect(row().style.right).toBe("24px");
	});

	it("rises 12px above the page's composer band", async () => {
		await attached();
		const release = registerComposerBand(at({ top: innerHeight - 76, height: 60 }));
		await flush();
		expect(row().style.bottom).toBe("88px");

		release();
		await flush();
		expect(row().style.bottom).toBe("24px");
	});
});
