// Two apps replace one page in every app: the router logs that clash in an app's shell, never
// on the index, where no list or record page opens.
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { registerContributions, registerStandardPages } from "@/contributions/registry";
import type { ReplacementContribution } from "@/contributions/types";
import { standardPages } from "@/pages/standardPages";
import { createShellRouter } from "@/router";

registerStandardPages(standardPages);

function declared(app: string): ReplacementContribution {
	return { app, doctype: "Note", key: "list", foreign: true, component: async () => ({}) };
}

vi.mock("virtual:frappe/contributions", () => ({
	default: {
		doctypes: [],
		pages: [],
		itemTypes: [],
		acts: [],
		replacements: [declared("crm"), declared("erpnext")],
	},
}));
vi.mock("@/pages/List.vue", () => ({ default: { render: () => null } }));
vi.mock("@/pages/Record.vue", () => ({ default: { render: () => null } }));
vi.mock("@/shell/NotFound.vue", () => ({ default: { render: () => null } }));

const addresses = new Addresses({ doctypes: { Note: ["note", ""] }, modules: {} });

function boot(app: string | null): Boot {
	const prefixes = app ? { [app]: { app, modular: false } } : {};
	return { app, shell_base: app ? `/apps/${app}` : "/apps", prefixes } as unknown as Boot;
}

let errors: ReturnType<typeof vi.spyOn>;

beforeAll(async () => {
	await registerContributions(["frappe", "crm", "erpnext"]);
});

beforeEach(() => {
	errors = vi.spyOn(console, "error").mockImplementation(() => {});
	return () => vi.restoreAllMocks();
});

describe("a replacement clash", () => {
	it("is logged once in an app's shell", () => {
		createShellRouter(boot("frappe"), addresses);

		expect(errors).toHaveBeenCalledOnce();
		expect(errors).toHaveBeenCalledWith(
			"[frappe] 2 apps replace the list page of 'Note' in 'frappe': 'erpnext' is used and " +
				"'crm' ignored."
		);
	});

	it("is not logged on the index", () => {
		createShellRouter(boot(null), addresses);

		expect(errors).not.toHaveBeenCalled();
	});
});
