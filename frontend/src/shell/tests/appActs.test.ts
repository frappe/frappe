// An app's global acts: imported from its `acts.js` at idle after the first paint, named
// `shell.<app>.<item>`, checked by their right, and waited for by an early dispatch or palette.
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, nextTick } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";
import type { Session } from "@framework/ui/api";

const state = vi.hoisted(() => ({ metas: {} as Record<string, any> }));

vi.mock("@framework/ui/api", async (importOriginal) => ({
	...(await importOriginal<typeof import("@framework/ui/api")>()),
	getTranslations: vi.fn(),
	getMeta: vi.fn(async (doctype: string) => ({ data: state.metas[doctype] ?? null, children: [] })),
}));

vi.mock("@/arrangement", async (importOriginal) => ({
	...(await importOriginal<typeof import("@/arrangement")>()),
	fetchArrangement: vi.fn().mockResolvedValue([]),
}));

import { resetDoctypeMeta } from "@framework/ui/useDoctypeMeta";
import { setSession } from "@framework/ui/useSession";
import { resetUserRoles } from "@framework/ui/useUserRoles";
import { ActDenied, acts, type ActItem } from "@/acts/dispatcher";
import { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { actsFiles, registerContributions } from "@/contributions/registry";
import type { ActsContribution } from "@/contributions/types";
import { installTranslate } from "@/i18n";
import { resetSprite } from "@/icons/sprite";
import { resetNavigationReports } from "@/navigation/registry";
import { registerShell } from "@/router/routeFor";
import AppShell from "../AppShell.vue";
import { paletteOpen } from "../palette";

const addresses = new Addresses({ doctypes: { "CRM Deal": ["crm-deal", "fcrm"] }, modules: {} });

const boot = {
	app: "crm",
	app_title: "CRM",
	shell_base: "/apps/crm",
	prefixes: { crm: { app: "crm", modular: false } },
	navigation: { rail: [], sidebars: {} },
	session: { user: { name: "sales@example.com", full_name: "Sales", email: "sales@example.com" } },
} as unknown as Boot;

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

async function shell() {
	const router = createRouter({
		history: createMemoryHistory(boot.shell_base),
		routes: [{ path: "/", name: "home", component: { render: () => null } }],
	});
	registerShell({ boot, addresses, router });
	const app = createApp(AppShell);
	installTranslate(app);
	app.provide("boot", boot);
	app.provide("addresses", addresses);
	app.use(router);
	await router.push("/");
	await router.isReady();
	app.mount(document.body.appendChild(document.createElement("div")));
	releases.push(() => app.unmount());
	await flush();
	return router;
}

/** Ships `exported` as `app`'s acts.js, loaded through the spy it returns. */
function ship(app: string, exported: unknown, gate?: Promise<void>) {
	const load = vi.fn(async () => {
		await gate;
		return { default: exported };
	});
	actsFiles.push({ app, load } satisfies ActsContribution);
	return load;
}

function deferred() {
	let open = () => {};
	const promise = new Promise<void>((resolve) => (open = resolve));
	return { promise, open };
}

function appActNames() {
	return acts
		.available()
		.map((act) => act.name)
		.filter((name) => name.split(".").length > 2);
}

function publishRoles(roles: string[]) {
	setSession({
		user: {
			name: "sales@example.com",
			full_name: "Sales",
			email: "sales@example.com",
			user_image: null,
			document_follow_notify: false,
		},
		roles,
		lang: "en",
		timezone: "Asia/Kolkata",
		defaults: {},
	} satisfies Session);
}

const logACall = (run: ActItem["run"] = () => {}): ActItem => ({
	name: "log_a_call",
	label: "Log a call",
	icon: "lucide-phone",
	run,
});

beforeAll(() => registerContributions(["frappe"]));

beforeEach(() => {
	actsFiles.length = 0;
	frames = [];
	vi.spyOn(window, "requestAnimationFrame").mockImplementation((frame) => frames.push(frame));
	vi.spyOn(console, "warn").mockImplementation(() => {});
	localStorage.clear();
	resetNavigationReports();
	resetSprite();
	resetDoctypeMeta();
	resetUserRoles();
	state.metas = {};
});

afterEach(() => {
	paletteOpen.value = false;
	releases.splice(0).forEach((release) => release());
	document.body.innerHTML = "";
	actsFiles.length = 0;
	vi.restoreAllMocks();
});

describe("an app's acts", () => {
	it("are named shell.<app>.<item>, and run with the shell and the value", async () => {
		const run = vi.fn();
		ship("crm", [logACall(run)]);
		ship("helpdesk", [logACall()]);
		const router = await shell();
		await paint();

		expect(appActNames()).toEqual(["shell.crm.log_a_call", "shell.helpdesk.log_a_call"]);
		await acts.run("shell.crm.log_a_call", "+91 98200 00000");
		expect(run).toHaveBeenCalledOnce();
		const [context, value] = run.mock.calls[0];
		expect(context.router).toBe(router);
		expect(typeof context.create).toBe("function");
		expect(value).toBe("+91 98200 00000");
		expect(acts.available().find((act) => act.name === "shell.crm.log_a_call")?.label).toBe(
			"Log a call"
		);
	});

	it("are imported at idle after the first paint, once", async () => {
		const load = ship("crm", [logACall()]);
		await shell();

		expect(load).not.toHaveBeenCalled();
		expect(appActNames()).toEqual([]);

		await paint();
		expect(load).toHaveBeenCalledOnce();
		expect(appActNames()).toEqual(["shell.crm.log_a_call"]);
	});

	it("make an act dispatched before the import finishes wait for it", async () => {
		const gate = deferred();
		const run = vi.fn();
		const load = ship("crm", [logACall(run)], gate.promise);
		await shell();

		const asked = acts.run("shell.crm.log_a_call");
		await flush();
		expect(load).toHaveBeenCalledOnce();
		expect(run).not.toHaveBeenCalled();

		gate.open();
		await asked;
		expect(run).toHaveBeenCalledOnce();
		await paint();
		expect(load).toHaveBeenCalledOnce();
	});

	it("make a name no app ships wait for the import, then refuse it as missing", async () => {
		const gate = deferred();
		const load = ship("crm", [logACall()], gate.promise);
		await shell();

		let settled = false;
		const asked = acts.run("shell.crm.nope").catch((error) => error);
		void asked.then(() => (settled = true));
		await flush();
		expect(load).toHaveBeenCalledOnce();
		expect(settled).toBe(false);

		gate.open();
		expect(await asked).toBeInstanceOf(ActDenied);
		expect(await asked).toMatchObject({ reason: "missing" });
	});

	it("never hold up the shell's own acts, present or missing", async () => {
		const load = ship("crm", [logACall()], new Promise(() => {}));
		await shell();

		await expect(acts.run("shell.theme", "dark")).resolves.toBeUndefined();
		await expect(acts.run("shell.nope")).rejects.toMatchObject({ reason: "missing" });
		expect(load).not.toHaveBeenCalled();
	});

	it("read their label each time, so a label from __() follows the messages", async () => {
		let label = "Log a call";
		ship("crm", [
			{
				...logACall(),
				get label() {
					return label;
				},
			},
		]);
		await shell();
		await paint();

		label = "Anruf erfassen";
		expect(acts.find("shell.crm.log_a_call")?.label).toBe("Anruf erfassen");
	});

	it("make the palette opened before the import finishes wait for it", async () => {
		const gate = deferred();
		ship("crm", [logACall()], gate.promise);
		await shell();

		await import("../ShellPalette.vue");
		paletteOpen.value = true;
		await flush();
		expect(document.querySelector("[data-slot='command-palette-input']")).toBeNull();

		gate.open();
		await vi.waitFor(
			() => expect(document.querySelector("[data-slot='command-palette-input']")).not.toBeNull(),
			{ timeout: 10000 }
		);
		expect(appActNames()).toEqual(["shell.crm.log_a_call"]);
	});

	it("pass a right on a named doctype by the reader's roles, and drop one with a bare ptype", async () => {
		publishRoles(["Sales User"]);
		state.metas["CRM Call Log"] = {
			name: "CRM Call Log",
			permissions: [{ role: "Sales User", permlevel: 0, read: 1, create: 1 }],
		};
		const run = vi.fn();
		ship("crm", [
			{ ...logACall(run), right: { doctype: "CRM Call Log", ptype: "create" } },
			{ ...logACall(run), name: "drop_call", right: { doctype: "CRM Call Log", ptype: "delete" } },
			{ ...logACall(run), name: "bare", right: "create" },
		]);
		await shell();
		await paint();

		await acts.run("shell.crm.log_a_call");
		expect(run).toHaveBeenCalledOnce();
		await expect(acts.run("shell.crm.drop_call")).rejects.toMatchObject({ reason: "right" });
		await expect(acts.run("shell.crm.bare")).rejects.toMatchObject({ reason: "missing" });
		expect(appActNames()).toEqual(["shell.crm.log_a_call"]);
		expect(console.warn).toHaveBeenCalledWith(
			"[frappe] shell.crm.bare is ignored: a shell act's right is { doctype, ptype }."
		);
	});

	it("skip what is no act, and lose only a broken app's acts", async () => {
		const error = vi.spyOn(console, "error").mockImplementation(() => {});
		actsFiles.push({ app: "broken", load: () => Promise.reject(new Error("syntax")) });
		ship("odd", { name: "not_a_list", run: () => {} });
		ship("crm", [{ name: "no_run", label: "No run" }, logACall()]);
		await shell();
		await paint();

		expect(appActNames()).toEqual(["shell.crm.log_a_call"]);
		expect(error.mock.calls[0][0]).toBe("[frappe] broken's acts.js did not load; it adds no act.");
		expect(console.warn).toHaveBeenCalledWith(
			"[frappe] odd's acts.js has no list as its default export; it adds no act."
		);
		expect(console.warn).toHaveBeenCalledWith(
			"[frappe] crm's acts.js holds an entry with no name or no run; it is ignored."
		);
	});
});
