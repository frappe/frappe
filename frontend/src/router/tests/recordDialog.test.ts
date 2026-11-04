// A record address of an opted-in doctype opens the dialog in the app, and the list on a direct load.
import { beforeEach, describe, expect, it, vi } from "vitest";

import { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { registerContributions, registerStandardPages } from "@/contributions/registry";
import { standardPages } from "@/pages/standardPages";
import { createShellRouter } from "@/router";
import { registerShell, routeFor } from "@/router/routeFor";
import {
	flushPendingRecordDialog,
	recordDialogRequests,
	registerRecordDialog,
} from "@/shell/recordDialog";

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
		recordDialogs: [
			{ app: "frappe", doctype: "ToDo", foreign: false },
			{ app: "frappe", doctype: "Quotation", foreign: false },
		],
	},
}));
vi.mock("@/pages/List.vue", () => ({ default: { render: () => null } }));
vi.mock("@/pages/Record.vue", () => ({ default: { render: () => null } }));
vi.mock("@/shell/NotFound.vue", () => ({ default: { render: () => null } }));

const addresses = new Addresses({
	doctypes: { ToDo: ["todo", "desk"], Note: ["note", "desk"], Quotation: ["quotation", "desk"], "Accounts Settings": ["accounts-settings", "desk"] },
	modules: { desk: "Desk" },
	singles: ["Accounts Settings"],
	submittables: ["Quotation"],
});
const boot = {
	app: "frappe",
	shell_base: "/apps/frappe",
	prefixes: { frappe: { app: "frappe", modular: false } },
} as unknown as Boot;

function open(path: string) {
	return recordDialogRequests.value.map(({ doctype, name, path }) => ({ doctype, name, path }));
}

describe("the record dialog guard", () => {
	let router: ReturnType<typeof createShellRouter>;

	beforeEach(async () => {
		router = createShellRouter(boot, addresses);
		registerShell({ boot, addresses, router });
		await router.push("/note");
		for (const request of [...recordDialogRequests.value]) request.dismiss();
	});

	it("opens the dialog over the page and keeps the URL", async () => {
		const failure = await router.push("/todo/TODO-1");

		expect(failure).toBeTruthy();
		expect(router.currentRoute.value.fullPath).toBe("/note");
		expect(open("")).toEqual([{ doctype: "ToDo", name: "TODO-1", path: "/note" }]);
	});

	it("opens one dialog for a record clicked twice", async () => {
		await router.push("/todo/TODO-1");
		await router.push("/todo/TODO-1");

		expect(open("")).toHaveLength(1);
	});

	it("opens the page when a saved new record replaces itself with its record", async () => {
		await router.push("/todo/new");
		await router.replace("/todo/TODO-1");

		expect(router.currentRoute.value.name).toBe("record");
		expect(open("")).toEqual([]);
	});

	it("drops the direct-load dialog when the first navigation fails", async () => {
		const fresh = createShellRouter(boot, addresses);
		fresh.beforeEach((to) => (to.name === "list" ? false : undefined));
		await fresh.push("/todo/TODO-1");
		await fresh.push("/note");

		expect(open("")).toEqual([]);
	});

	it("opens the page for a doctype that did not opt in", async () => {
		await router.push("/note/NOTE-1");

		expect(router.currentRoute.value.name).toBe("record");
		expect(open("")).toEqual([]);
	});

	it("shows the list first on a direct load, then opens the dialog over it", async () => {
		const fresh = createShellRouter(boot, addresses);
		await fresh.push("/todo/TODO-1");
		flushPendingRecordDialog(fresh.currentRoute.value.fullPath);

		expect(fresh.currentRoute.value.name).toBe("list");
		expect(open("")).toEqual([{ doctype: "ToDo", name: "TODO-1", path: "/todo" }]);
	});

	it("leaves a single to its page", async () => {
		await router.push("/accounts-settings/Accounts%20Settings");

		expect(router.currentRoute.value.name).toBe("record");
		expect(open("")).toEqual([]);
	});

	it("leaves a submittable to its page: the dialog has no Submit or Cancel", async () => {
		await router.push("/quotation/QTN-1");

		expect(router.currentRoute.value.name).toBe("record");
		expect(open("")).toEqual([]);
	});

	it("keeps the standard address for the full page", async () => {
		await router.push(routeFor("ToDo", "TODO-1", { standard: true }));

		expect(router.currentRoute.value.name).toBe("standard-record");
		expect(open("")).toEqual([]);
	});
});
