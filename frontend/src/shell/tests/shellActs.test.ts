// The shell surface: each shell act run by name, which acts the shell holds where, and the log out it confirms.
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, nextTick, type App } from "vue";
import { createMemoryHistory, createRouter, type Router } from "vue-router";

import { acts, ActDenied } from "@/acts/dispatcher";
import { Addresses } from "@/addresses";
import type { Boot, NavigationItem } from "@/boot";
import { registerContributions } from "@/contributions/registry";
import { registerShell } from "@/router/routeFor";
import { resetNavigationReports } from "@/navigation/registry";
import { resetSprite } from "@/icons/sprite";
import AppShell from "../AppShell.vue";
import { closeCreates, createRequests, registerCreateDialog } from "../create";

const fake = vi.hoisted(() => ({ logout: vi.fn(), runMethod: vi.fn() }));

vi.mock("@framework/ui/api", async (importOriginal) => ({
	...(await importOriginal<typeof import("@framework/ui/api")>()),
	logout: fake.logout,
	runMethod: fake.runMethod,
}));

vi.mock("frappe-ui", async (importOriginal) => ({
	...(await importOriginal<typeof import("frappe-ui")>()),
	toast: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("@/arrangement", async (importOriginal) => ({
	...(await importOriginal<typeof import("@/arrangement")>()),
	fetchArrangement: vi.fn().mockResolvedValue([]),
}));

const addresses = new Addresses({
	doctypes: { "Sales Invoice": ["sales-invoice", "accounts"] },
	modules: { accounts: "Accounts" },
});

const stub = { render: () => null };

const accounts: NavigationItem = {
	key: "accounts",
	item_type: "Sidebar",
	link_to: "module_def_accounts",
	label: "Accounts",
};
const sidebars = {
	module_def_accounts: [{ key: "invoice", item_type: "DocType", link_to: "Sales Invoice" }],
};

const session = {
	user: { name: "jane@example.com", full_name: "Jane Doe", email: "jane@example.com" },
};

const inApp = {
	app: "crm",
	shell_base: "/apps/crm",
	prefixes: { crm: { app: "crm", modular: false } },
	navigation: { rail: [accounts], sidebars },
	session,
} as unknown as Boot;

const onIndex = {
	app: null,
	shell_base: "/apps",
	prefixes: { crm: { app: "crm", modular: false } },
	session,
	apps: [],
} as unknown as Boot;

const mounted: App[] = [];

async function flush() {
	await Promise.resolve();
	await Promise.resolve();
	await nextTick();
}

/** A hash write and a pop both land a task later. */
async function settle() {
	for (let turn = 0; turn < 3; turn++) {
		await new Promise((resolve) => setTimeout(resolve, 0));
		await flush();
	}
}

async function shell(boot: Boot = inApp, path = "/sales-invoice"): Promise<{ host: HTMLElement; router: Router }> {
	const router = createRouter({
		history: createMemoryHistory(),
		routes: [
			{ path: "/", name: "home", component: stub },
			{ path: "/:doctype", name: "list", component: stub },
		],
	});
	registerShell({ boot, addresses, router });
	const host = document.createElement("div");
	document.body.appendChild(host);
	const app = createApp(AppShell);
	app.provide("boot", boot);
	app.provide("addresses", addresses);
	app.use(router);
	await router.push(path);
	await router.isReady();
	app.mount(host);
	mounted.push(app);
	await flush();
	return { host, router };
}

function shellActNames() {
	return acts
		.available()
		.map((act) => act.name)
		.filter((name) => name.startsWith("shell."));
}

beforeAll(async () => {
	registerCreateDialog(stub);
	await registerContributions(["frappe"]);
});

beforeEach(() => {
	localStorage.clear();
	window.history.replaceState(null, "", "/");
	resetNavigationReports();
	resetSprite();
	vi.clearAllMocks();
});

afterEach(() => {
	closeCreates();
	mounted.splice(0).forEach((app) => app.unmount());
	document.body.innerHTML = "";
	vi.restoreAllMocks();
});

describe("the acts the shell holds", () => {
	it("in an app: the rail's, the sidebar's toggle, settings, the person's and Create", async () => {
		await shell();
		expect(shellActNames()).toEqual([
			"shell.all_apps",
			"shell.customize_sidebar",
			"shell.copy_link",
			"shell.toggle_sidebar",
			"shell.open_settings",
			"shell.my_settings",
			"shell.theme",
			"shell.desk_v1",
			"shell.log_out",
			"shell.create",
		]);
	});

	it("on the index: none of the rail's, as no rail draws there", async () => {
		await shell(onIndex, "/");
		expect(shellActNames()).toEqual([
			"shell.open_settings",
			"shell.my_settings",
			"shell.theme",
			"shell.desk_v1",
			"shell.log_out",
			"shell.create",
		]);
	});

	it("no toggle while no sidebar shows", async () => {
		await shell(inApp, "/");
		expect(shellActNames()).not.toContain("shell.toggle_sidebar");
		await expect(acts.run("shell.toggle_sidebar")).rejects.toMatchObject({ reason: "missing" });
	});

	it("asks Create for a doctype and Settings for a pane, from the palette's places", async () => {
		await shell();
		const find = (name: string) => acts.available().find((act) => act.name === name)!;

		expect(find("shell.create").palette).toBeUndefined();
		fake.runMethod.mockImplementation(async (method: string) => ({
			data:
				method === "frappe.shell.palette.places"
					? {
							doctypes: [
								{ name: "Sales Invoice", app: "crm", route: `${inApp.shell_base}/sales-invoice`, can_create: true },
								{ name: "Lead", app: "crm", route: `${inApp.shell_base}/lead`, can_create: false },
							],
							apps: [],
							titles: { crm: "CRM" },
					  }
					: { panes: [{ app: "crm", key: "deals", label: "Deals", blocks: [] }], index: [], titles: { crm: "CRM" } },
		}));

		expect(await find("shell.create").argument!.options("")).toEqual([
			{ value: "Sales Invoice", label: "Sales Invoice", description: "CRM" },
		]);
		expect(await find("shell.open_settings").argument!.options("")).toEqual([
			{ value: { prefix: "crm", pane: "deals" }, label: "Deals", description: "CRM" },
		]);
	});

	it("lets go of the surface when the shell unmounts", async () => {
		await shell();
		mounted.splice(0).forEach((app) => app.unmount());
		expect(shellActNames()).toEqual([]);
	});
});

describe("each shell act, run by name", () => {
	it("all_apps, my_settings and desk_v1 leave for their pages", async () => {
		const assign = vi.spyOn(window.location, "assign").mockImplementation(() => {});
		await shell();

		await acts.run("shell.all_apps");
		expect(assign).toHaveBeenLastCalledWith("/apps");
		await acts.run("shell.my_settings");
		expect(assign).toHaveBeenLastCalledWith("/app/user/jane%40example.com");
		await acts.run("shell.desk_v1");
		expect(assign).toHaveBeenLastCalledWith("/app");
	});

	it("customize_sidebar opens the rail's customize dialog", async () => {
		const { router } = await shell();
		await acts.run("shell.customize_sidebar");
		await settle();
		expect(router.currentRoute.value.hash).toBe("#customize/rail");
	});

	it("open_settings writes the settings address it is given, or none", async () => {
		const { router } = await shell();
		await acts.run("shell.open_settings", { prefix: "desk", pane: "profile" });
		await settle();
		expect(router.currentRoute.value.hash).toBe("#settings/desk/profile");

		router.go(-1);
		await settle();
		await acts.run("shell.open_settings");
		await settle();
		expect(router.currentRoute.value.hash).toBe("#settings");
	});

	it("copy_link copies the page's link and says so", async () => {
		const writeText = vi.fn().mockResolvedValue(undefined);
		vi.stubGlobal("navigator", { clipboard: { writeText } });
		const { toast } = await import("frappe-ui");
		await shell();

		await acts.run("shell.copy_link");
		expect(writeText).toHaveBeenCalledWith(`${window.location.origin}/sales-invoice`);
		expect(toast.success).toHaveBeenCalledWith("Link copied");
		vi.unstubAllGlobals();
	});

	it("toggle_sidebar collapses and expands the open sidebar, and its label follows", async () => {
		const { host } = await shell();
		const panel = () => host.querySelector("[data-slot='sidebar']")!.getAttribute("data-state");
		const label = () => acts.available().find((act) => act.name === "shell.toggle_sidebar")?.label;
		expect(label()).toBe("Collapse sidebar");

		await acts.run("shell.toggle_sidebar");
		await flush();
		expect(panel()).toBe("collapsed");
		expect(label()).toBe("Expand sidebar");
		expect(host.querySelector("[aria-label='Expand sidebar']")).not.toBeNull();

		await acts.run("shell.toggle_sidebar");
		await flush();
		expect(panel()).toBe("expanded");
	});

	it("theme takes a scheme from its argument's options, and refuses any other value", async () => {
		await shell();
		const theme = acts.available().find((act) => act.name === "shell.theme")!;
		expect(await theme.argument!.options("")).toEqual([
			{ value: "light", label: "Light" },
			{ value: "dark", label: "Dark" },
			{ value: "system", label: "System" },
		]);

		await acts.run("shell.theme", "dark");
		expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
		await expect(acts.run("shell.theme", "sepia")).rejects.toThrow("Theme is light, dark or system");
		await acts.run("shell.theme", "light");
		expect(document.documentElement.getAttribute("data-theme")).toBe("light");
	});

	it("create opens Create for a doctype, with or without starting values", async () => {
		await shell();
		void acts.run("shell.create", "ToDo");
		void acts.run("shell.create", { doctype: "Note", values: { title: "Hello" } });
		await flush();

		expect(createRequests.value.map(({ doctype, values }) => ({ doctype, values }))).toEqual([
			{ doctype: "ToDo", values: {} },
			{ doctype: "Note", values: { title: "Hello" } },
		]);
		await expect(acts.run("shell.create")).rejects.toThrow("Create needs a doctype");
	});

	it("an act the shell does not hold is denied as missing", async () => {
		await shell();
		const denied = await acts.run("shell.nope").catch((error) => error);
		expect(denied).toBeInstanceOf(ActDenied);
		expect(denied).toMatchObject({ act: "shell.nope", reason: "missing" });
	});
});

describe("log_out", () => {
	function button(label: string) {
		return Array.from(document.body.querySelector("[role='dialog']")!.querySelectorAll("button")).find(
			(node) => node.textContent?.trim() === label
		)!;
	}

	it("asks first, and Cancel keeps the session", async () => {
		const assign = vi.spyOn(window.location, "assign").mockImplementation(() => {});
		fake.logout.mockResolvedValue({ data: null });
		await shell();

		await acts.run("shell.log_out");
		await flush();
		const dialog = document.body.querySelector<HTMLElement>("[role='dialog']")!;
		expect(dialog.textContent).toContain("Log out?");
		expect(dialog.textContent).toContain("You will need to sign in again.");

		button("Cancel").click();
		await flush();
		expect(document.body.querySelector("[role='dialog']")).toBeNull();
		expect(fake.logout).not.toHaveBeenCalled();
		expect(assign).not.toHaveBeenCalled();
	});

	it("logs out on confirmation and goes to login with the way back, hash dropped", async () => {
		const assign = vi.spyOn(window.location, "assign").mockImplementation(() => {});
		fake.logout.mockResolvedValue({ data: null });
		await shell();
		window.history.replaceState(null, "", "/crm-deal?sidebar=fcrm#customize/rail");

		await acts.run("shell.log_out");
		await flush();
		button("Log out").click();
		await flush();
		await flush();

		expect(fake.logout).toHaveBeenCalled();
		expect(assign).toHaveBeenCalledWith("/login?redirect-to=%2Fcrm-deal%3Fsidebar%3Dfcrm");
	});

	it("keeps the dialog and toasts when the log out fails", async () => {
		const assign = vi.spyOn(window.location, "assign").mockImplementation(() => {});
		const { toast } = await import("frappe-ui");
		fake.logout.mockRejectedValueOnce(new Error("offline"));
		await shell();

		await acts.run("shell.log_out");
		await flush();
		button("Log out").click();
		await flush();
		await flush();

		expect(document.body.querySelector("[role='dialog']")).not.toBeNull();
		expect(toast.error).toHaveBeenCalledWith("Could not log out");
		expect(assign).not.toHaveBeenCalled();
	});
});
