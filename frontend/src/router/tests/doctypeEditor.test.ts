// The DocType editor holds /doctype/<name> on a flat prefix. The DocType list, its saved
// views and the standard record page keep their addresses, and a modular prefix is untouched.
import { describe, expect, it, vi } from "vitest";

import { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { registerStandardPages } from "@/contributions/registry";
import { standardPages } from "@/pages/standardPages";
import { createShellRouter } from "@/router";
import { registerShell, routeFor, routeForNew } from "@/router/routeFor";

registerStandardPages(standardPages);

vi.mock("@/pages/List.vue", () => ({ default: { render: () => null } }));
vi.mock("@/pages/Record.vue", () => ({ default: { render: () => null } }));
vi.mock("@/shell/NotFound.vue", () => ({ default: { render: () => null } }));
vi.mock("@/pages/doctypeEditor/DoctypeEditor.vue", () => ({ default: { render: () => null } }));

const addresses = new Addresses({
	doctypes: { DocType: ["doctype", "core"], User: ["user", "core"] },
	modules: { core: "Core" },
	singles: [],
});

function boot(modular: boolean): Boot {
	return {
		app: "frappe",
		shell_base: "/apps/frappe",
		prefixes: { frappe: { app: "frappe", modular } },
	} as unknown as Boot;
}

async function routeOf(path: string, modular = false) {
	const router = createShellRouter(boot(modular), addresses);
	await router.push(path);
	return router.currentRoute.value;
}

describe("the DocType editor's address", () => {
	it("opens the editor for a DocType", async () => {
		const route = await routeOf("/doctype/User");
		expect(route.name).toBe("doctype-editor");
		expect(route.params.name).toBe("User");
	});

	it("opens the editor for a new DocType", async () => {
		const route = await routeOf("/doctype/new");
		expect(route.name).toBe("doctype-editor");
		expect(route.params.name).toBe("new");
	});

	it("leaves the DocType list and its saved views alone", async () => {
		expect((await routeOf("/doctype")).name).toBe("list");
		expect((await routeOf("/doctype/view/list")).name).toBe("standard-list");
	});

	it("leaves the standard record page alone", async () => {
		const route = await routeOf("/doctype/User/record");
		expect(route.name).toBe("standard-record");
		expect(route.params.name).toBe("User");
	});

	it("leaves a modular prefix alone", async () => {
		expect((await routeOf("/core/doctype/User", true)).name).toBe("record");
	});

	it("links a DocType record to the editor, and its standard address to the record page", () => {
		const router = createShellRouter(boot(false), addresses);
		registerShell({ boot: boot(false), addresses, router });
		const editor = router.resolve(routeFor("DocType", "User"));
		expect([editor.name, editor.path]).toEqual(["doctype-editor", "/doctype/User"]);
		const record = router.resolve(routeFor("DocType", "User", { standard: true }));
		expect([record.name, record.path]).toEqual(["standard-record", "/doctype/User/record"]);
	});

	it("opens a new DocType in the editor by name and by address alike", async () => {
		const router = createShellRouter(boot(false), addresses);
		registerShell({ boot: boot(false), addresses, router });
		await router.push(routeForNew("DocType"));
		expect([router.currentRoute.value.name, router.currentRoute.value.path]).toEqual([
			"doctype-editor",
			"/doctype/new",
		]);
		expect((await routeOf("/doctype/new")).name).toBe("doctype-editor");
		expect(router.resolve(routeForNew("User")).name).toBe("new-record");
	});

	it("carries a duplicate's source and Edit full form's values to the editor", async () => {
		const router = createShellRouter(boot(false), addresses);
		registerShell({ boot: boot(false), addresses, router });
		await router.push(routeForNew("DocType", { __copy_of: "ToDo", module: "Desk" }));
		expect(router.currentRoute.value.fullPath).toBe("/doctype/new?__copy_of=ToDo&module=Desk");
	});
});
