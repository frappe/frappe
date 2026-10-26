// The record a Link field opens: its main address, so a replacement page wins, and none for a doctype with no address.
import { describe, expect, it, vi } from "vitest";

import { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { registerStandardPages } from "@/contributions/registry";
import { standardPages } from "@/pages/standardPages";
import { createShellRouter } from "@/router";
import { recordLink } from "@/router/recordLink";
import { registerShell } from "@/router/routeFor";

registerStandardPages(standardPages);

vi.mock("@/pages/Home.vue", () => ({ default: { render: () => null } }));
vi.mock("@/pages/List.vue", () => ({ default: { render: () => null } }));
vi.mock("@/pages/Record.vue", () => ({ default: { render: () => null } }));
vi.mock("@/shell/NotFound.vue", () => ({ default: { render: () => null } }));

const addresses = new Addresses({
	doctypes: { "Sales Invoice": ["sales-invoice", "accounts"] },
	modules: { accounts: "Accounts" },
});

function setup(modular: boolean) {
	const boot = {
		app: "erpnext",
		shell_base: "/apps/erpnext",
		prefixes: { erpnext: { app: "erpnext", modular } },
	} as unknown as Boot;
	const router = createShellRouter(boot, addresses);
	registerShell({ boot, addresses, router });
	return { router, link: recordLink(router) };
}

describe.each([
	{ shape: "flat", modular: false, prefix: "" },
	{ shape: "modular", modular: true, prefix: "/accounts" },
])("a record link on a $shape app", ({ modular, prefix }) => {
	it("gives the record's main address", () => {
		const { link } = setup(modular);

		expect(link.href("Sales Invoice", "SI/001")).toBe(
			`/apps/erpnext${prefix}/sales-invoice/SI%2F001`
		);
	});

	it("gives no address for a doctype with none", () => {
		const { link } = setup(modular);

		expect(link.href("Secret DocType", "X-1")).toBeNull();
	});

	it("opens the record in the same tab", async () => {
		const { router, link } = setup(modular);
		await router.push(`${prefix}/sales-invoice`);

		link.open("Sales Invoice", "SI-002");
		await vi.waitFor(() => expect(router.currentRoute.value.name).toBe("record"));

		expect(router.currentRoute.value.params.name).toBe("SI-002");
	});
});
