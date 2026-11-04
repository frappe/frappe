// `shell.open` and `shell.href`: the act and its two shorthands go through `routeFor` and the router, so
// the record dialog's guard covers them.
import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import { effectScope, type EffectScope } from "vue";

import { acts, ActDenied } from "@/acts/dispatcher";
import { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { registerContributions, registerStandardPages } from "@/contributions/registry";
import { standardPages } from "@/pages/standardPages";
import { createShellRouter } from "@/router";
import { registerShell, urlFor } from "@/router/routeFor";
import { recordDialogRequests, registerRecordDialog } from "../recordDialog";
import { useShellActs, type Shell } from "../shellActs";

registerStandardPages(standardPages);
registerContributions(["frappe"]);
registerRecordDialog({ render: () => null });

vi.mock("virtual:frappe/contributions", () => ({
	default: {
		doctypes: [],
		pages: [],
		itemTypes: [],
		viewTypes: [],
		acts: [],
		replacements: [],
		recordDialogs: [{ app: "frappe", doctype: "ToDo", foreign: false }],
	},
}));
vi.mock("@/pages/List.vue", () => ({ default: { render: () => null } }));
vi.mock("@/pages/Record.vue", () => ({ default: { render: () => null } }));
vi.mock("@/shell/NotFound.vue", () => ({ default: { render: () => null } }));

const addresses = new Addresses({
	doctypes: { ToDo: ["todo", "desk"], Note: ["note", "desk"], "Note Settings": ["note-settings", "desk"] },
	modules: { desk: "Desk" },
	singles: ["Note Settings"],
	submittables: [],
});
const boot = {
	app: "frappe",
	shell_base: "/apps/frappe",
	prefixes: { frappe: { app: "frappe", modular: false } },
	session: { user: { name: "jane@example.com" } },
} as unknown as Boot;

let scope: EffectScope;
let router: ReturnType<typeof createShellRouter>;
let shell: Shell;

beforeEach(async () => {
	router = createShellRouter(boot, addresses);
	registerShell({ boot, addresses, router });
	await router.push("/note");
	scope = effectScope();
	shell = scope.run(() =>
		useShellActs({ boot, router, openSettings: () => {}, confirmLogout: () => {} }).shell
	)!;
});

afterEach(() => {
	scope.stop();
	for (const request of [...recordDialogRequests.value]) request.dismiss();
});

describe("shell.open", () => {
	it("opens a record page, a list and a saved view", async () => {
		await shell.open("Note", "NOTE-1");
		expect(router.currentRoute.value.fullPath).toBe("/note/NOTE-1");

		await shell.open("Note");
		expect(router.currentRoute.value.fullPath).toBe("/note");

		await shell.open("Note", null, { view: "mine" });
		expect(router.currentRoute.value.fullPath).toBe("/note/view/mine");
	});

	it("is the act shell.open, which a script names and the palette does not list", async () => {
		await acts.run("shell.open", { doctype: "Note", name: "NOTE-2" });
		expect(router.currentRoute.value.fullPath).toBe("/note/NOTE-2");
		expect(acts.find("shell.open")?.palette).toBe(false);
	});

	it("opens a record of a doctype that opted in as a dialog over the page", async () => {
		await shell.open("ToDo", "TODO-1");

		expect(router.currentRoute.value.fullPath).toBe("/note");
		expect(recordDialogRequests.value.map(({ doctype, name }) => ({ doctype, name }))).toEqual([
			{ doctype: "ToDo", name: "TODO-1" },
		]);
	});

	it("opens a single's document, with or without a name, and a name wins over a view", async () => {
		await shell.open("Note Settings");
		expect(router.currentRoute.value.params).toMatchObject({ doctype: "note-settings", name: "Note Settings" });

		await shell.open("Note", "NOTE-1", { view: "mine" });
		expect(router.currentRoute.value.fullPath).toBe("/note/NOTE-1");
	});

	it("rejects a value with no doctype, and a doctype with no address", async () => {
		await expect(acts.run("shell.open", {})).rejects.toThrow("Open needs a doctype");
		await expect(shell.open("Nope")).rejects.toThrow("no address for doctype 'Nope'");
	});

	it("is denied as missing while no shell is mounted", async () => {
		scope.stop();
		const denied = await shell.open("Note").catch((error) => error);
		expect(denied).toBeInstanceOf(ActDenied);
		expect(denied).toMatchObject({ act: "shell.open", reason: "missing" });
	});
});

describe("shell.href", () => {
	it("is the address of a record or a list, and null when the doctype has none", () => {
		expect(shell.href("Note", "NOTE-1")).toBe(urlFor("Note", "NOTE-1"));
		expect(shell.href("Note")).toBe(urlFor("Note"));
		expect(shell.href("Note", "NOTE-1")).not.toBe(shell.href("Note"));
		expect(shell.href("Nope", "X")).toBeNull();
	});
});
