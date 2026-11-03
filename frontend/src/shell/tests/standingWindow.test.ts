// A standing window: what an app's shell hook attaches with `shell.window`, drawn by the shell's row.
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { toast } from "frappe-ui";
import { logout as endSession } from "@framework/ui/api";
import { createApp, defineComponent, h, nextTick, onUnmounted, type Component } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";

vi.mock("@framework/ui/api", async (importOriginal) => ({
	...(await importOriginal<typeof import("@framework/ui/api")>()),
	getTranslations: vi.fn(),
	getMeta: vi.fn(async () => ({ data: null, children: [] })),
	logout: vi.fn(async () => {}),
}));
vi.mock("frappe-ui", async (importOriginal) => {
	const actual = await importOriginal<typeof import("frappe-ui")>();
	return { ...actual, toast: Object.assign(vi.fn(), actual.toast) };
});

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
import type { PaletteContext } from "../paletteGroups";
import { openPlace } from "../palettePlaces";
import { loadDocument } from "../tabKeepAlive";
import { logout } from "../session";

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

/** Ships `app` with one window of `component`, and gives back its handle once the hook ran and the lazy row drew it. */
async function attached(
	component: Component = Body,
	options: StandingWindowOptions = { icon: "lucide-phone", width: 280 }
) {
	let handle: StandingWindowHandle | undefined;
	ship("crm", (shell) => (handle = shell.window(component, options)));
	await mount();
	await vi.waitFor(() => expect(document.querySelector("[data-standing-window]")).not.toBeNull());
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

	describe("title tooltip", () => {
		const hasTooltip = (element: HTMLElement) => element.hasAttribute("data-slot");
		const frameTitle = () => frame().querySelector<HTMLElement>("[data-standing-title]")!;

		/** Makes the frame title measure `scroll`px of text in a 100px box. */
		const measureTitleAs = (scroll: number) =>
			vi.spyOn(HTMLElement.prototype, "scrollWidth", "get").mockImplementation(function (
				this: HTMLElement
			) {
				return this.hasAttribute("data-standing-title") ? scroll : 0;
			});

		beforeEach(() => {
			vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockReturnValue(100);
		});

		it("has none on the pill", async () => {
			const handle = await attached();
			handle.setTitle("Alice · Calling…");
			handle.minimise();
			await nextTick();
			const restore = pill().querySelector<HTMLElement>("[data-standing-restore]")!;
			expect(restore.textContent).toContain("Alice · Calling…");
			expect(hasTooltip(restore)).toBe(false);
		});

		it("shows on the frame title only while the title is truncated", async () => {
			const scroll = measureTitleAs(100);
			const handle = await attached();
			handle.open();
			handle.setTitle("Alice");
			await vi.waitFor(() => expect(frameTitle().textContent!.trim()).toBe("Alice"));
			expect(hasTooltip(frameTitle())).toBe(false);

			scroll.mockImplementation(() => 180);
			handle.setTitle("Alice Wonderland-Smith · Calling…");
			await vi.waitFor(() => expect(hasTooltip(frameTitle())).toBe(true));

			scroll.mockImplementation(() => 100);
			handle.setTitle("Alice");
			await vi.waitFor(() => expect(hasTooltip(frameTitle())).toBe(false));
		});

		it("stays while a truncated title ticks", async () => {
			measureTitleAs(180);
			const handle = await attached();
			handle.open();
			handle.setTitle("Alice Wonderland-Smith · 00:42");
			await vi.waitFor(() => expect(hasTooltip(frameTitle())).toBe(true));
			const trigger = frameTitle();

			handle.setTitle("Alice Wonderland-Smith · 00:43");
			await nextTick();
			await nextTick();
			expect(hasTooltip(frameTitle())).toBe(true);
			expect(frameTitle()).toBe(trigger);
		});
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

	it("pads the pill's right edge like its left unless actions sit there, and the frame 16px", async () => {
		const handle = await attached();
		expect(pill().classList).toContain("pr-3.5");
		expect(pill().classList).not.toContain("pr-1.5");
		handle.setActions([{ label: "Mute", icon: "lucide-mic-off", run: vi.fn() }]);
		await nextTick();
		expect(pill().classList).toContain("pr-1.5");
		expect(pill().classList).not.toContain("pr-3.5");

		expect(header().classList).toContain("px-4");
		expect(header().classList).toContain("pt-4");
		expect(frame().querySelector("[data-call-note]")!.parentElement!.classList).toContain("p-4");
	});

	it("never narrows the pill while the title changes", async () => {
		const reports: ResizeObserverCallback[] = [];
		vi.stubGlobal(
			"ResizeObserver",
			class {
				constructor(report: ResizeObserverCallback) {
					reports.push(report);
				}
				observe() {}
				unobserve() {}
				disconnect() {}
			}
		);
		await attached();
		const widthNow = async (width: number) => {
			const entry = { target: pill(), borderBoxSize: [{ inlineSize: width }] };
			reports.forEach((report) =>
				report([entry as unknown as ResizeObserverEntry], {} as ResizeObserver)
			);
			await nextTick();
		};

		await widthNow(121);
		expect(pill().style.minWidth).toBe("min(121px, calc(100vw - 48px))");
		await widthNow(120);
		expect(pill().style.minWidth).toBe("min(121px, calc(100vw - 48px))");
		await widthNow(130);
		expect(pill().style.minWidth).toBe("min(130px, calc(100vw - 48px))");
		vi.unstubAllGlobals();
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

	it("pulses the pill while the app sets attention", async () => {
		const handle = await attached();
		handle.open();
		await nextTick();
		handle.minimise();
		await nextTick();
		const pill = () => document.querySelector("[data-standing-minimised]")!;
		expect(pill().classList.contains("standing-attention")).toBe(false);

		handle.setAttention(true);
		await nextTick();
		expect(pill().classList.contains("standing-attention")).toBe(true);

		handle.setAttention(false);
		await nextTick();
		expect(pill().classList.contains("standing-attention")).toBe(false);

		handle.setAttention(1 as unknown as boolean);
		await nextTick();
		expect(pill().classList.contains("standing-attention")).toBe(true);
	});

	it.each([
		[100, "240px"],
		[320, "320px"],
		[900, "400px"],
		[undefined, "280px"],
	])("clamps a width of %s to %s", async (width, drawn) => {
		await attached(Body, { icon: "lucide-phone", width });
		expect(frame().parentElement!.style.width).toBe(drawn);
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

	it("moves focus to the pill or the frame only after the user's own click", async () => {
		const handle = await attached();
		handle.open();
		await nextTick();

		frame().querySelector<HTMLElement>("[data-standing-minimise]")!.click();
		await flush();
		expect(document.activeElement).toBe(pill().querySelector("[data-standing-restore]"));

		pill().click();
		await flush();
		expect(document.activeElement).toBe(frame().querySelector("[data-standing-minimise]"));

		const field = document.body.appendChild(document.createElement("input"));
		field.focus();
		handle.minimise();
		await flush();
		handle.open();
		await flush();
		expect(document.activeElement).toBe(field);
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
	afterEach(() => {
		vi.unstubAllGlobals();
		document.querySelectorAll("flow-launcher").forEach((host) => host.remove());
	});

	const row = () => document.querySelector<HTMLElement>("[data-standing-row]")!;
	const at = (rect: Partial<DOMRect>) => {
		const element = document.body.appendChild(document.createElement("div"));
		const { left = 0, top = 0, width = 0, height = 0 } = rect;
		const box = { left, top, width, height, right: left + width, bottom: top + height };
		element.getBoundingClientRect = () => box as DOMRect;
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
		const release = registerComposerBand(
			at({ left: 0, width: innerWidth, top: innerHeight - 76, height: 60 })
		);
		await flush();
		expect(row().style.bottom).toBe("88px");

		release();
		await flush();
		expect(row().style.bottom).toBe("24px");
	});

	it("stays on the bottom line when the band lies wholly to its left", async () => {
		await attached();
		row().getBoundingClientRect = () => ({ left: innerWidth - 304, width: 280 }) as DOMRect;
		window.dispatchEvent(new Event("resize"));
		const release = registerComposerBand(
			at({ left: 100, width: 600, top: innerHeight - 76, height: 60 })
		);
		await flush();
		expect(row().style.bottom).toBe("24px");
		release();
	});

	it("stops at the shell's left margin when the composer is dragged far left", async () => {
		await attached();
		row().getBoundingClientRect = () => ({ left: 0, width: 280 }) as DOMRect;
		window.dispatchEvent(new Event("resize"));
		const release = registerFloatingComposer(at({ left: 40, width: 460, top: 100 }));
		await flush();
		expect(row().style.right).toBe(`${innerWidth - 24 - 280}px`);
		release();
	});

	describe("on a narrow screen", () => {
		const APPS = [CRM, HELPDESK, { app: "hr", title: "HR" }];
		const FRAME = 400;
		const PILL = 150;
		const GAP = 12;

		/** Each app's window at `FRAME` wide when open and `PILL` when minimised, as a browser would lay out the row. */
		async function threeApps(width: number) {
			const handles: Record<string, StandingWindowHandle | undefined> = {};
			for (const { app } of APPS)
				ship(app, (shell) => (handles[app] = shell.window(Body, { width: FRAME })));
			vi.stubGlobal("innerWidth", width);
			await mount(APPS);
			await vi.waitFor(() => expect(document.querySelector("[data-standing-row]")).not.toBeNull());
			const sizes = () =>
				APPS.map(({ app }) => {
					const open = shown(frame(app));
					return { app, open, pill: shown(pill(app)) && !open, wide: open ? FRAME : PILL };
				}).filter((entry) => entry.open || entry.pill);
			const total = () => sizes().reduce((sum, { wide }) => sum + wide + GAP, -GAP);
			row().getBoundingClientRect = () => ({ width: total() }) as DOMRect;
			return { handles, sizes, total };
		}

		it("minimises the open windows from the left until the row fits, so no frame leaves the screen", async () => {
			const { handles, sizes, total } = await threeApps(1024);
			for (const { app } of APPS) handles[app]!.open();
			await flush();

			expect(sizes().map(({ app, open }) => [app, open])).toEqual([
				["crm", false],
				["helpdesk", true],
				["hr", true],
			]);
			expect(total()).toBeLessThanOrEqual(1024 - 48);
			expect(1024 - parseFloat(row().style.right) - total()).toBeGreaterThanOrEqual(24);
			expect(parseFloat(row().style.right)).toBeGreaterThanOrEqual(24);
			expect(handles.crm!.state).toBe("minimised");
		});

		it("spares the window just opened, even the leftmost", async () => {
			const { handles, sizes } = await threeApps(1024);
			handles.helpdesk!.open();
			handles.hr!.open();
			await flush();
			handles.crm!.open();
			await flush();

			expect(sizes().map(({ app, open }) => [app, open])).toEqual([
				["crm", true],
				["helpdesk", false],
				["hr", true],
			]);
		});

		it("minimises one window after another while the row still does not fit", async () => {
			const { handles, sizes } = await threeApps(800);
			for (const { app } of APPS) handles[app]!.open();
			await flush();
			expect(sizes().map(({ app, open }) => [app, open])).toEqual([
				["crm", false],
				["helpdesk", false],
				["hr", true],
			]);
		});

		it("keeps the last open frame when the pills alone still overflow", async () => {
			const { handles, sizes } = await threeApps(700);
			for (const { app } of APPS) handles[app]!.open();
			await flush();
			expect(sizes().filter(({ open }) => open).map(({ app }) => app)).toEqual(["hr"]);
			expect(handles.hr!.state).toBe("open");
		});

		it("minimises from the left, sparing the rightmost, when the window shrinks", async () => {
			const { handles, sizes } = await threeApps(1440);
			for (const { app } of APPS) handles[app]!.open();
			await flush();
			vi.stubGlobal("innerWidth", 1024);
			window.dispatchEvent(new Event("resize"));
			await flush();
			expect(sizes().map(({ app, open }) => [app, open])).toEqual([
				["crm", false],
				["helpdesk", true],
				["hr", true],
			]);
		});

		it("leaves the row alone while it fits", async () => {
			const { handles, sizes } = await threeApps(1440);
			for (const { app } of APPS) handles[app]!.open();
			await flush();
			expect(sizes().every(({ open }) => open)).toBe(true);
		});

		it("caps the row at the viewport less the margins", async () => {
			await threeApps(390);
			expect(row().style.maxWidth).toBe("342px");
		});
	});

	/** The Flow launcher: its shadow root holds the button, 44px at the bottom right, and the closed panel. */
	const launcher = (rect: Partial<DOMRect> = {}) => {
		const host = document.body.appendChild(document.createElement("flow-launcher"));
		const root = host.attachShadow({ mode: "open" });
		const icon = root.appendChild(document.createElement("button"));
		icon.className = "icon";
		const { left = innerWidth - 60, top = innerHeight - 60, width = 44, height = 44 } = rect;
		const box = { left, top, width, height, right: left + width, bottom: top + height };
		icon.getBoundingClientRect = () => box as DOMRect;
		const panel = root.appendChild(document.createElement("div"));
		panel.className = "panel";
		panel.setAttribute("inert", "");
		panel.dataset.mode = "float";
		return { host, icon, panel };
	};
	const dockRight = (panel: HTMLElement, icon: HTMLElement, width = 420) => {
		panel.getBoundingClientRect = () => ({ left: innerWidth - width, right: innerWidth, width }) as DOMRect;
		icon.hidden = true;
		icon.getBoundingClientRect = () => ({ left: 0, top: 0, right: 0, bottom: 0, width: 0 }) as DOMRect;
		panel.dataset.mode = "right";
		panel.removeAttribute("inert");
	};

	it("sits 12px left of the Flow launcher, on the same bottom line", async () => {
		const { icon } = launcher();
		await attached();
		expect(row().style.right).toBe("72px");
		expect(row().style.bottom).toBe("24px");

		icon.hidden = true;
		icon.getBoundingClientRect = () => ({ left: 0, top: 0, right: 0, bottom: 0, width: 0 }) as DOMRect;
		await flush();
		expect(row().style.right).toBe("24px");
	});

	it("finds a launcher that loads after the shell and follows its drag", async () => {
		await attached();
		row().getBoundingClientRect = () => ({ left: innerWidth - 304, width: 280, height: 36 }) as DOMRect;
		window.dispatchEvent(new Event("resize"));
		await flush();
		expect(row().style.right).toBe("24px");
		const { icon } = launcher();
		await flush();
		expect(row().style.right).toBe("72px");

		icon.getBoundingClientRect = () =>
			({ left: 16, right: 60, top: innerHeight - 60, bottom: innerHeight - 16, width: 44 }) as DOMRect;
		icon.style.left = "16px";
		await flush();
		expect(row().style.right).toBe("24px");
	});

	it("sits left of the launcher when it is further left than a floating composer", async () => {
		launcher({ left: innerWidth - 700 });
		await attached();
		row().getBoundingClientRect = () => ({ left: innerWidth - 776, width: 280, height: 36 }) as DOMRect;
		window.dispatchEvent(new Event("resize"));
		const release = registerFloatingComposer(at({ left: innerWidth - 484, top: 100 }));
		await flush();
		expect(row().style.right).toBe("712px");

		release();
	});

	it("sits left of a floating composer when it is further left than the launcher", async () => {
		launcher();
		await attached();
		const release = registerFloatingComposer(at({ left: innerWidth - 484, top: 100 }));
		await flush();
		expect(row().style.right).toBe("496px");

		release();
	});

	it("ignores a launcher above a pill, but not one beside an open frame", async () => {
		launcher({ top: 300 });
		await attached();
		row().getBoundingClientRect = () => ({ left: innerWidth - 304, width: 280, height: 36 }) as DOMRect;
		window.dispatchEvent(new Event("resize"));
		await flush();
		expect(row().style.right).toBe("24px");

		row().getBoundingClientRect = () => ({ left: innerWidth - 304, width: 280, height: 600 }) as DOMRect;
		window.dispatchEvent(new Event("resize"));
		await flush();
		expect(row().style.right).toBe(`${innerWidth - (innerWidth - 60) + 12}px`);
	});

	it("ignores a launcher wholly left of the row", async () => {
		launcher({ left: 100 });
		await attached();
		row().getBoundingClientRect = () => ({ left: innerWidth - 304, width: 280, height: 36 }) as DOMRect;
		window.dispatchEvent(new Event("resize"));
		await flush();
		expect(row().style.right).toBe("24px");
	});

	it("stops at the shell's left margin when the launcher is dragged far left", async () => {
		launcher({ left: 40 });
		await attached();
		row().getBoundingClientRect = () => ({ left: 0, width: 1000, height: 36 }) as DOMRect;
		window.dispatchEvent(new Event("resize"));
		await flush();
		expect(row().style.right).toBe(`${innerWidth - 24 - 1000}px`);
	});

	it("keeps 12px from a launcher that starts just left of a composer's edge", async () => {
		launcher({ left: innerWidth - 490 });
		await attached();
		row().getBoundingClientRect = () => ({ left: innerWidth - 776, width: 280, height: 36 }) as DOMRect;
		window.dispatchEvent(new Event("resize"));
		const release = registerFloatingComposer(at({ left: innerWidth - 484, top: 100 }));
		await flush();
		expect(row().style.right).toBe("502px");
		release();
	});

	it("sits 12px left of the Flow panel docked on the right, and goes back when it undocks or closes", async () => {
		const { icon, panel } = launcher();
		await attached();
		expect(row().style.right).toBe("72px");

		dockRight(panel, icon);
		await flush();
		expect(row().style.right).toBe("432px");
		expect(row().style.bottom).toBe("24px");

		panel.getBoundingClientRect = () => ({ left: innerWidth - 500, width: 500 }) as DOMRect;
		panel.style.setProperty("--width", "500px");
		await flush();
		expect(row().style.right).toBe("512px");

		panel.dataset.mode = "float";
		await flush();
		expect(row().style.right).toBe("24px");

		panel.dataset.mode = "right";
		await flush();
		expect(row().style.right).toBe("512px");

		panel.setAttribute("inert", "");
		icon.hidden = false;
		icon.getBoundingClientRect = () =>
			({
				left: innerWidth - 60,
				right: innerWidth - 16,
				top: innerHeight - 60,
				bottom: innerHeight - 16,
				width: 44,
			}) as DOMRect;
		await flush();
		expect(row().style.right).toBe("72px");
	});

	it("follows a window resize while the panel is docked", async () => {
		const { icon, panel } = launcher();
		dockRight(panel, icon);
		await attached();
		expect(row().style.right).toBe("432px");

		panel.getBoundingClientRect = () => ({ left: innerWidth - 640, width: 640 }) as DOMRect;
		window.dispatchEvent(new Event("resize"));
		await flush();
		expect(row().style.right).toBe("652px");
	});

	it("sits left of a floating composer that is further left than the docked panel", async () => {
		const { icon, panel } = launcher();
		dockRight(panel, icon);
		await attached();
		row().getBoundingClientRect = () => ({ left: innerWidth - 776, width: 280, height: 36 }) as DOMRect;
		window.dispatchEvent(new Event("resize"));
		const release = registerFloatingComposer(at({ left: innerWidth - 600, top: 100 }));
		await flush();
		expect(row().style.right).toBe("612px");
		release();
	});

	it("leaves a panel docked on the left or full screen to the row's own place", async () => {
		const { icon, panel } = launcher();
		dockRight(panel, icon);
		panel.dataset.mode = "left";
		await attached();
		expect(row().style.right).toBe("24px");
		panel.dataset.mode = "full";
		await flush();
		expect(row().style.right).toBe("24px");
	});

	it("finds a panel that is already docked when the shell loads", async () => {
		const { icon, panel } = launcher();
		dockRight(panel, icon);
		await attached();
		expect(row().style.right).toBe("432px");
	});
});

describe("keep-alive", () => {
	const away = (href = "/elsewhere/todo") => {
		const link = document.body.appendChild(document.createElement("a"));
		link.href = href;
		return link;
	};
	// Whether the shell prevented the click: a later listener stops the test document from navigating.
	const prevented = (link: Element, init: MouseEventInit = {}) => {
		let seen = false;
		const last = (event: Event) => {
			seen = event.defaultPrevented;
			event.preventDefault();
		};
		document.addEventListener("click", last);
		link.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, ...init }));
		document.removeEventListener("click", last);
		return seen;
	};
	const leaving = () => {
		const event = new Event("beforeunload", { cancelable: true });
		window.dispatchEvent(event);
		return event.defaultPrevented;
	};

	let opened: ReturnType<typeof vi.spyOn>;
	let assigned: ReturnType<typeof vi.spyOn>;

	beforeEach(() => {
		opened = vi.spyOn(window, "open").mockImplementation(() => ({ opener: window }) as Window);
		assigned = vi.spyOn(window.location, "assign").mockImplementation(() => {});
	});

	it("is off until the app sets it: a link to another prefix loads here and a reload does not ask", async () => {
		await attached();
		expect(prevented(away())).toBe(false);
		expect(opened).not.toHaveBeenCalled();
		expect(leaving()).toBe(false);
		loadDocument("/apps");
		expect(assigned).toHaveBeenCalledWith("/apps");
	});

	it("opens a link to another prefix in a new tab while it is on", async () => {
		const handle = await attached();
		handle.setKeepAlive(true);
		await flush();
		expect(prevented(away())).toBe(true);
		expect(opened).toHaveBeenCalledWith(`${location.origin}/elsewhere/todo`, "_blank", "noopener");
	});

	it("asks before a reload or a tab close while it is on", async () => {
		const handle = await attached();
		handle.setKeepAlive(true);
		await flush();
		expect(leaving()).toBe(true);
	});

	it("loads a page the shell opens by address in a new tab while it is on", async () => {
		const handle = await attached();
		handle.setKeepAlive(true);
		await flush();
		loadDocument("/apps");
		expect(opened).toHaveBeenCalledWith("/apps", "_blank");
		expect(assigned).not.toHaveBeenCalled();
	});

	it("leaves a link the router moves, a new-tab click, a download and a hash change alone", async () => {
		const handle = await attached();
		handle.setKeepAlive(true);
		await flush();
		const routed = away("/elsewhere/leads");
		routed.addEventListener("click", (event) => event.preventDefault());
		const blank = away();
		blank.target = "_blank";
		const download = away("/files/a.pdf");
		download.setAttribute("download", "");
		for (const link of [routed, blank, download, away("#note"), away("mailto:a@example.com")])
			prevented(link);
		prevented(away(), { ctrlKey: true });
		prevented(away(), { button: 1 });
		expect(opened).not.toHaveBeenCalled();
	});

	it("goes back to loading here and not asking when the app sets it off", async () => {
		const handle = await attached();
		handle.setKeepAlive(true);
		await flush();
		handle.setKeepAlive(false);
		await flush();
		expect(prevented(away())).toBe(false);
		expect(leaving()).toBe(false);
		loadDocument("/apps");
		expect(assigned).toHaveBeenCalledWith("/apps");
	});

	it("holds the tab while any window has it on", async () => {
		const handles: Record<string, StandingWindowHandle | undefined> = {};
		ship("crm", (shell) => (handles.crm = shell.window(Body)));
		ship("helpdesk", (shell) => (handles.helpdesk = shell.window(Body)));
		await mount([CRM, HELPDESK]);
		await vi.waitFor(() => expect(handles.helpdesk).toBeDefined());
		handles.crm!.setKeepAlive(true);
		handles.helpdesk!.setKeepAlive(true);
		await flush();
		handles.crm!.setKeepAlive(false);
		await flush();
		expect(leaving()).toBe(true);
		handles.helpdesk!.setKeepAlive(false);
		await flush();
		expect(leaving()).toBe(false);
	});

	it("opens a link that targets the top of this tab in a new tab", async () => {
		const handle = await attached();
		handle.setKeepAlive(true);
		await flush();
		const link = away("/elsewhere/top");
		link.target = "_top";
		expect(prevented(link)).toBe(true);
		expect(opened).toHaveBeenCalledTimes(1);
	});

	it("opens a place on another prefix from the palette in a new tab while it is on", async () => {
		const handle = await attached();
		handle.setKeepAlive(true);
		await flush();
		openPlace("/elsewhere/todo", { boot, router: { push: vi.fn() } } as unknown as PaletteContext);
		expect(opened).toHaveBeenCalledWith("/elsewhere/todo", "_blank");
		expect(assigned).not.toHaveBeenCalled();
	});

	it("logs out without the unload prompt while it is on", async () => {
		const handle = await attached();
		handle.setKeepAlive(true);
		await flush();
		await logout();
		expect(leaving()).toBe(false);
		expect(assigned).toHaveBeenCalledWith(expect.stringMatching(/^\/login\?redirect-to=/));
	});

	it("keeps the unload prompt when the logout call fails", async () => {
		const handle = await attached();
		handle.setKeepAlive(true);
		await flush();
		vi.mocked(endSession).mockRejectedValueOnce(new Error("offline"));
		await expect(logout()).rejects.toThrow("offline");
		expect(leaving()).toBe(true);
	});

	it("toasts a link that opens the address when the browser blocks the new tab", async () => {
		const handle = await attached();
		handle.setKeepAlive(true);
		await flush();
		opened.mockImplementationOnce(() => null);
		loadDocument("/app/todo/new");
		const [message, options] = vi.mocked(toast).mock.calls.at(-1)!;
		expect(message).toBe("Your browser blocked the new tab");
		expect(assigned).not.toHaveBeenCalled();
		(options!.action as { onClick: (event: MouseEvent) => void }).onClick({} as MouseEvent);
		expect(opened).toHaveBeenLastCalledWith("/app/todo/new", "_blank", "noopener");
	});

	it("replaces the blocked-tab toast when a second tab is blocked", async () => {
		const handle = await attached();
		handle.setKeepAlive(true);
		await flush();
		opened.mockImplementation(() => null);
		loadDocument("/apps");
		loadDocument("/app/todo/new");
		const calls = vi.mocked(toast).mock.calls.slice(-2);
		expect(calls[0][1]!.id).toBe(calls[1][1]!.id);
	});

	it("shows no toast when the new tab opened, and cuts its opener", async () => {
		const handle = await attached();
		handle.setKeepAlive(true);
		await flush();
		const tab = { opener: window } as Window;
		opened.mockImplementationOnce(() => tab);
		vi.mocked(toast).mockClear();
		loadDocument("/apps");
		expect(toast).not.toHaveBeenCalled();
		expect(tab.opener).toBeNull();
	});

	it("lets the tab go when the shell unmounts", async () => {
		const handle = await attached();
		handle.setKeepAlive(true);
		await flush();
		releases.splice(0).forEach((release) => release());
		expect(leaving()).toBe(false);
		loadDocument("/apps");
		expect(assigned).toHaveBeenCalledWith("/apps");
	});

	it("reads anything but true as off", async () => {
		const handle = await attached();
		handle.setKeepAlive(true);
		handle.setKeepAlive(undefined as unknown as boolean);
		await flush();
		expect(leaving()).toBe(false);
	});
});

describe("dragging", () => {
	const wrapper = () => frame().parentElement!;
	const press = (target: Element, x: number, y: number) =>
		target.dispatchEvent(
			new PointerEvent("pointerdown", {
				bubbles: true,
				button: 0,
				clientX: x,
				clientY: y,
			})
		);
	const move = (x: number, y: number) =>
		window.dispatchEvent(
			new PointerEvent("pointermove", { clientX: x, clientY: y })
		);
	const release = () => window.dispatchEvent(new PointerEvent("pointerup"));
	/** Gives `element` the box it would have standing in the row, 24px above the bottom at the right. */
	const standing = (element: HTMLElement, width: number, height: number) => {
		const left = innerWidth - 24 - width;
		const bottom = innerHeight - 24;
		element.getBoundingClientRect = () =>
			({
				left,
				bottom,
				width,
				height,
				right: left + width,
				top: bottom - height,
			} as DOMRect);
	};

	async function open() {
		const handle = await attached();
		handle.open();
		await flush();
		standing(wrapper(), 280, 200);
		return handle;
	}

	it("moves an open window by its header, out of the row", async () => {
		await open();
		press(header(), 800, 600);
		move(700, 500);
		await flush();

		expect(wrapper().classList.contains("fixed")).toBe(true);
		expect(wrapper().style.left).toBe(`${innerWidth - 24 - 280 - 100}px`);
		expect(wrapper().style.bottom).toBe("124px");
	});

	it("stays in the row for a move under 4px", async () => {
		await open();
		press(header(), 800, 600);
		move(802, 602);
		release();
		await flush();

		expect(wrapper().classList.contains("fixed")).toBe(false);
	});

	it("keeps the window inside the 24px margin", async () => {
		await open();
		press(header(), 800, 600);
		move(-5000, -5000);
		await flush();
		expect(wrapper().style.left).toBe("24px");
		expect(wrapper().style.bottom).toBe(`${innerHeight - 24 - 200}px`);

		move(9000, 9000);
		await flush();
		expect(wrapper().style.left).toBe(`${innerWidth - 24 - 280}px`);
		expect(wrapper().style.bottom).toBe("24px");
	});

	it("does not start a drag from a header button", async () => {
		const handle = await open();
		handle.setActions([{ label: "Mute", icon: "lucide-mic", run: vi.fn() }]);
		await flush();
		press(frame().querySelector("[data-standing-action]")!, 800, 600);
		move(700, 500);
		await flush();

		expect(wrapper().classList.contains("fixed")).toBe(false);
	});

	it("puts the window back in the row on a double-click of the header", async () => {
		await open();
		press(header(), 800, 600);
		move(700, 500);
		release();
		await flush();
		header().dispatchEvent(new MouseEvent("dblclick", { bubbles: true }));
		await flush();

		expect(wrapper().classList.contains("fixed")).toBe(false);
		expect(wrapper().style.left).toBe("");
	});

	it("moves a pill by its body without restoring it, and restores on a plain click", async () => {
		const handle = await open();
		handle.minimise();
		await flush();
		standing(pill(), 120, 40);

		press(pill(), 900, 740);
		move(800, 640);
		release();
		pill().click();
		await flush();
		expect(handle.state).toBe("minimised");
		expect(pill().classList.contains("fixed")).toBe(true);
		expect(pill().style.left).toBe(`${innerWidth - 24 - 120 - 100}px`);
		expect(pill().style.bottom).toBe("124px");

		press(pill(), 900, 740);
		release();
		pill().click();
		await flush();
		expect(handle.state).toBe("open");
	});

	it("opens a dragged pill's window at the same place", async () => {
		const handle = await open();
		handle.minimise();
		await flush();
		standing(pill(), 120, 40);
		press(pill(), 900, 740);
		move(800, 640);
		release();
		handle.open();
		await flush();

		expect(wrapper().style.bottom).toBe("124px");
	});

	it("keeps room for a frame above a pill dragged to the top", async () => {
		const handle = await open();
		handle.minimise();
		await flush();
		standing(pill(), 120, 40);
		press(pill(), 900, 740);
		move(900, -5000);
		release();
		handle.open();
		await flush();

		expect(wrapper().style.bottom).toBe(`${innerHeight - 24 - 160}px`);
		expect(frame().style.maxHeight).toBe("160px");
	});
});
