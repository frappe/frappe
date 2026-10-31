// An app's shell hook: its `setup(shell)` runs once per tab at idle after the first paint, in the
// site's app order, only for the apps boot permits, and a broken hook is logged and skipped.
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, nextTick } from "vue";
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

import { runAfterSave } from "@/afterSave";
import { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { registerContributions, shellHookFiles } from "@/contributions/registry";
import type { ShellHookContribution } from "@/contributions/types";
import { installTranslate } from "@/i18n";
import { resetSprite } from "@/icons/sprite";
import { resetNavigationReports } from "@/navigation/registry";
import { registerShell } from "@/router/routeFor";
import AppShell from "../AppShell.vue";

const addresses = new Addresses({ doctypes: {}, modules: {} });

const appBoot = {
	app: "crm",
	app_title: "CRM",
	shell_base: "/apps/crm",
	prefixes: { crm: { app: "crm", modular: false } },
	navigation: { rail: [], sidebars: {} },
	session: { user: { name: "sales@example.com", full_name: "Sales", email: "sales@example.com" } },
} as unknown as Boot;

const indexBoot = { ...appBoot, app: null, shell_base: "/apps", navigation: undefined } as Boot;

const releases: (() => void)[] = [];
let frames: FrameRequestCallback[] = [];

async function flush() {
	for (let turn = 0; turn < 3; turn++) {
		await new Promise((resolve) => setTimeout(resolve, 0));
		await nextTick();
	}
}

/** Lets the frame the shell waits on paint, and the idle time after it pass. */
async function paint() {
	frames.splice(0).forEach((frame) => frame(performance.now()));
	await flush();
}

async function mount(shellHooks: string[], boot: Boot = appBoot) {
	const booted = { ...boot, shell_hooks: shellHooks } as Boot;
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
}

/** Ships `module` as `app`'s shell.js, loaded through the spy it returns. */
function ship(app: string, module: Record<string, unknown>, gate?: Promise<void>) {
	const load = vi.fn(async () => {
		await gate;
		return module;
	});
	shellHookFiles.push({ app, load } satisfies ShellHookContribution);
	return load;
}

function deferred() {
	let open = () => {};
	const promise = new Promise<void>((resolve) => (open = resolve));
	return { promise, open };
}

function errors() {
	return vi.mocked(console.error).mock.calls.map(([message]) => String(message));
}

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
});

afterEach(() => {
	releases.splice(0).forEach((release) => release());
	document.body.innerHTML = "";
	shellHookFiles.length = 0;
	vi.restoreAllMocks();
});

describe("the shell hook", () => {
	it("is imported at idle after the first paint, not before", async () => {
		const setup = vi.fn();
		const load = ship("crm", { setup });

		await mount(["crm"]);
		expect(load).not.toHaveBeenCalled();

		await paint();
		expect(load).toHaveBeenCalledOnce();
		expect(setup).toHaveBeenCalledOnce();
	});

	it("runs only for the apps boot permits", async () => {
		const permitted = ship("crm", { setup: vi.fn() });
		const refused = ship("helpdesk", { setup: vi.fn() });

		await mount(["crm"]);
		await paint();

		expect(permitted).toHaveBeenCalledOnce();
		expect(refused).not.toHaveBeenCalled();
	});

	it("adds no idle work when no permitted app ships one", async () => {
		await mount([]);
		const baseline = frames.length;
		releases.splice(0).forEach((release) => release());
		frames = [];

		const load = ship("helpdesk", { setup: vi.fn() });
		await mount(["crm"]);
		expect(frames.length).toBe(baseline);

		await paint();
		expect(load).not.toHaveBeenCalled();
	});

	it("runs each setup in the site's app order, whichever file loads first", async () => {
		const order: string[] = [];
		const slow = deferred();
		ship("crm", { setup: () => order.push("crm") }, slow.promise);
		ship("helpdesk", { setup: () => order.push("helpdesk") });

		await mount(["crm", "helpdesk"]);
		await paint();
		expect(order).toEqual([]);

		slow.open();
		await flush();
		expect(order).toEqual(["crm", "helpdesk"]);
	});

	it("runs on the /apps index too", async () => {
		const setup = vi.fn();
		ship("crm", { setup });

		await mount(["crm"], indexBoot);
		await paint();

		expect(setup).toHaveBeenCalledOnce();
	});

	it("hands setup a frozen shell that holds only afterSave", async () => {
		let shell: Record<string, unknown> | undefined;
		ship("crm", { setup: (given: Record<string, unknown>) => (shell = given) });

		await mount(["crm"]);
		await paint();

		expect(Object.keys(shell!)).toEqual(["afterSave"]);
		expect(Object.isFrozen(shell)).toBe(true);
	});

	it("registers an after-save handler that runs when its doctype saves", async () => {
		const handler = vi.fn();
		ship("crm", {
			setup: (shell: { afterSave: (doctype: string, run: typeof handler) => void }) =>
				shell.afterSave("FCRM Settings", handler),
		});

		await mount(["crm"]);
		await paint();
		const saved = { doctype: "FCRM Settings", name: "FCRM Settings", doc: {}, changed: [] };
		runAfterSave(saved);
		runAfterSave({ ...saved, doctype: "User" });

		expect(handler).toHaveBeenCalledOnce();
		expect(handler).toHaveBeenCalledWith(saved);
	});
});

describe("a broken shell hook", () => {
	it("that throws is logged and skipped, and the next app's still runs", async () => {
		ship("crm", {
			setup: () => {
				throw new Error("boom");
			},
		});
		const next = vi.fn();
		ship("helpdesk", { setup: next });

		await mount(["crm", "helpdesk"]);
		await paint();

		expect(errors()).toEqual(["[frappe] crm's shell.js setup failed; it is skipped."]);
		expect(next).toHaveBeenCalledOnce();
	});

	it("whose setup rejects is logged", async () => {
		ship("crm", { setup: async () => Promise.reject(new Error("later")) });

		await mount(["crm"]);
		await paint();

		expect(errors()).toEqual(["[frappe] crm's shell.js setup failed; it is skipped."]);
	});

	it("with no setup export is logged and skipped", async () => {
		ship("crm", { default: () => {} });
		const next = vi.fn();
		ship("helpdesk", { setup: next });

		await mount(["crm", "helpdesk"]);
		await paint();

		expect(errors()).toEqual(["[frappe] crm's shell.js exports no setup function; it is skipped."]);
		expect(next).toHaveBeenCalledOnce();
	});

	it("that does not load is logged and skipped", async () => {
		shellHookFiles.push({ app: "crm", load: () => Promise.reject(new Error("404")) });
		const next = vi.fn();
		ship("helpdesk", { setup: next });

		await mount(["crm", "helpdesk"]);
		await paint();

		expect(errors()).toEqual(["[frappe] crm's shell.js did not load; it is skipped."]);
		expect(next).toHaveBeenCalledOnce();
	});
});
