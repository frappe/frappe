// A single has no list. Its list address, typed by hand or followed from an old link, lands
// on the document itself, under both route shapes.
import { describe, expect, it, vi } from "vitest";

import { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { createShellRouter } from "@/router";

vi.mock("@/pages/Home.vue", () => ({ default: { render: () => null } }));
vi.mock("@/pages/List.vue", () => ({ default: { render: () => null } }));
vi.mock("@/pages/Record.vue", () => ({ default: { render: () => null } }));
vi.mock("@/pages/Module.vue", () => ({ default: { render: () => null } }));
vi.mock("@/shell/NotFound.vue", () => ({ default: { render: () => null } }));

const addresses = new Addresses({
	doctypes: {
		"Sales Invoice": ["sales-invoice", "accounts"],
		"Accounts Settings": ["accounts-settings", "accounts"],
	},
	modules: { accounts: "Accounts", selling: "Selling" },
	singles: ["Accounts Settings"],
});

function boot(modular: boolean): Boot {
	return {
		app: "erpnext",
		shell_base: "/apps/erpnext",
		prefixes: { erpnext: { app: "erpnext", modular } },
	} as Boot;
}

describe("a single's list address", () => {
	it("opens the document itself", async () => {
		const router = createShellRouter(boot(false), addresses);
		await router.push("/accounts-settings?layout=Compact");

		expect(router.currentRoute.value.name).toBe("record");
		expect(router.currentRoute.value.params).toEqual({
			doctype: "accounts-settings",
			name: "Accounts Settings",
		});
		// Context survives the redirect; only the path changed.
		expect(router.currentRoute.value.query).toEqual({ layout: "Compact" });
	});

	it("opens the document itself under a modular prefix", async () => {
		const router = createShellRouter(boot(true), addresses);
		await router.push("/accounts/accounts-settings");

		expect(router.currentRoute.value.name).toBe("record");
		expect(router.currentRoute.value.params).toEqual({
			module: "accounts",
			doctype: "accounts-settings",
			name: "Accounts Settings",
		});
	});

	it("still corrects a wrong module segment on the second pass", async () => {
		const router = createShellRouter(boot(true), addresses);
		await router.push("/selling/accounts-settings");

		expect(router.currentRoute.value.name).toBe("record");
		expect(router.currentRoute.value.params).toEqual({
			module: "accounts",
			doctype: "accounts-settings",
			name: "Accounts Settings",
		});
	});

	it("drops a saved view, which a single cannot have", async () => {
		const router = createShellRouter(boot(false), addresses);
		await router.push("/accounts-settings/view/list/open");

		expect(router.currentRoute.value.name).toBe("record");
		expect(router.currentRoute.value.params.name).toBe("Accounts Settings");
	});

	it("leaves an ordinary doctype's list alone", async () => {
		const router = createShellRouter(boot(false), addresses);
		await router.push("/sales-invoice");

		expect(router.currentRoute.value.name).toBe("list");
	});
});
