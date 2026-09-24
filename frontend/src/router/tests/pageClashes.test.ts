// A page whose slug a doctype or module already holds gets no route, and neither do two pages
// of one app that share a slug.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import type { PageContribution } from "@/contributions/types";
import { itemContext } from "@/navigation/context";
import { createShellRouter } from "@/router";

const fake = vi.hoisted(() => ({ pages: [] as PageContribution[] }));

vi.mock("virtual:frappe/contributions", () => ({
	default: { doctypes: [], pages: fake.pages, itemTypes: [], replacements: [] },
}));
vi.mock("@/pages/Home.vue", () => ({ default: { render: () => null } }));
vi.mock("@/pages/List.vue", () => ({ default: { render: () => null } }));
vi.mock("@/pages/Record.vue", () => ({ default: { render: () => null } }));
vi.mock("@/pages/Module.vue", () => ({ default: { render: () => null } }));
vi.mock("@/shell/NotFound.vue", () => ({ default: { render: () => null } }));

const addresses = new Addresses({
	doctypes: {
		Lead: ["lead", "selling"],
		"Sales Invoice": ["sales-invoice", "accounts"],
	},
	modules: { accounts: "Accounts", selling: "Selling" },
});

function page(slug: string, app = "crm"): PageContribution {
	return { app, slug, component: async () => ({ render: () => null }) };
}

function boot(modular: boolean, app = "crm"): Boot {
	return {
		app,
		shell_base: `/apps/${app}`,
		prefixes: { [app]: { app, modular } },
	} as Boot;
}

let errors: ReturnType<typeof vi.spyOn>;

beforeEach(() => {
	errors = vi.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => {
	fake.pages.splice(0);
	vi.restoreAllMocks();
});

function pageNames(modular: boolean) {
	const router = createShellRouter(boot(modular), addresses);
	return router
		.getRoutes()
		.map((route) => String(route.name))
		.filter((name) => name.startsWith("page:"));
}

describe("a page on a flat prefix", () => {
	it("is dropped when a doctype has its slug, and the doctype keeps the address", async () => {
		fake.pages.push(page("lead"), page("deals"));
		const router = createShellRouter(boot(false), addresses);

		await router.push("/lead");

		expect(router.currentRoute.value.name).toBe("list");
		expect(router.currentRoute.value.params.doctype).toBe("lead");
		expect(pageNames(false)).toEqual(["page:crm:deals"]);
		expect(errors).toHaveBeenCalledWith(
			expect.stringContaining("the page 'lead' of 'crm' is dropped: the doctype 'Lead'")
		);
	});

	it("keeps a slug that is only a module's", () => {
		fake.pages.push(page("selling"));

		expect(pageNames(false)).toEqual(["page:crm:selling"]);
		expect(errors).not.toHaveBeenCalled();
	});
});

describe("a page on a modular prefix", () => {
	it("is dropped when a module has its slug", () => {
		fake.pages.push(page("accounts"), page("deals"));

		expect(pageNames(true)).toEqual(["page:crm:deals"]);
		expect(errors).toHaveBeenCalledWith(
			expect.stringContaining("the page 'accounts' of 'crm' is dropped: the module 'Accounts'")
		);
	});

	it("keeps a slug that is only a doctype's", () => {
		fake.pages.push(page("lead"));

		expect(pageNames(true)).toEqual(["page:crm:lead"]);
		expect(errors).not.toHaveBeenCalled();
	});
});

describe("two pages of one app with one slug", () => {
	it("are both dropped, with one error", () => {
		fake.pages.push(page("deals"), page("deals"), page("inbox"));

		expect(pageNames(false)).toEqual(["page:crm:inbox"]);
		expect(errors).toHaveBeenCalledTimes(1);
		expect(errors).toHaveBeenCalledWith(
			expect.stringContaining("'crm' ships more than one page named 'deals'")
		);
	});

	it("are not a clash when they belong to two apps", () => {
		fake.pages.push(page("deals"), page("deals", "helpdesk"));

		expect(pageNames(false)).toEqual(["page:crm:deals"]);
		expect(errors).not.toHaveBeenCalled();
	});
});

describe("the pages a navigation item can link to", () => {
	it("leave out a dropped page, whose route does not exist", () => {
		fake.pages.push(page("lead"), page("deals"), page("deals", "helpdesk"));
		const router = createShellRouter(boot(false), addresses);

		const { pages } = itemContext(boot(false), addresses, router, [], {});

		expect(pages.map((entry) => `${entry.app}/${entry.slug}`)).toEqual(["crm/deals"]);
	});
});
