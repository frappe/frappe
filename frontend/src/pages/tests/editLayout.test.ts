// Who sees the "Edit layout" entries, and the editor route each opens.
import { describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";

vi.mock("@/router/routeFor", () => ({
	routeFor: (doctype: string, name: string, options: { query: Record<string, string> }) => ({
		name: "doctype-editor",
		doctype,
		params: { name },
		query: options.query,
	}),
}));

import { useEditLayoutRoute } from "../editLayout";

const standard = { name: "Sales Invoice" };

const blank = { render: () => null };
const EDITOR = [{ path: "/doctype/:name", name: "doctype-editor", component: blank }];
const INDEX = [{ path: "/", name: "home", component: blank }];

function routeWith(boot: Record<string, unknown>, meta: Record<string, unknown> | null, routes = EDITOR) {
	let route!: ReturnType<typeof useEditLayoutRoute>;
	const app = createApp(
		defineComponent({
			setup() {
				route = useEditLayoutRoute(() => meta as any);
				return () => h("div");
			},
		})
	);
	app.use(createRouter({ history: createMemoryHistory(), routes }));
	app.provide("boot", boot);
	app.mount(document.createElement("div"));
	return route;
}

const appBoot = { developer_mode: false, session: { roles: ["System Manager"] } };

describe("useEditLayoutRoute", () => {
	it("opens the editor at the layout, and at the row when one is named", () => {
		const route = routeWith(appBoot, standard);
		expect(route("side-panel")).toMatchObject({ params: { name: "Sales Invoice" }, query: { layout: "side-panel" } });
		expect(route("details", "app:1")).toMatchObject({ query: { layout: "details", row: "app:1" } });
	});

	it("names the mode the editor opens in, and Customize for a site row, which Design on an app's DocType does not read", () => {
		const developer = routeWith({ ...appBoot, developer_mode: true }, standard);
		expect(developer("details")).toMatchObject({ query: { mode: "design" } });
		expect(developer("details", "app:1")).toMatchObject({ query: { mode: "design" } });
		expect(developer("details", "5021")).toMatchObject({ query: { mode: "customize", row: "5021" } });
		expect(routeWith(appBoot, standard)("details")).toMatchObject({ query: { mode: "customize" } });
		expect(routeWith(appBoot, { name: "Task Note", custom: 1 })("details", "5021")).toMatchObject({
			query: { mode: "design" },
		});
	});

	it("keeps a standard Single shut outside developer mode, and opens it to Design in it", () => {
		const single = { name: "Print Settings", issingle: 1 };
		expect(routeWith(appBoot, single)("details")).toBeNull();
		expect(routeWith({ ...appBoot, developer_mode: true }, single)("details")).toMatchObject({
			query: { mode: "design" },
		});
	});

	it("refuses anyone without the System Manager role, developer mode or not", () => {
		const user = { developer_mode: true, session: { roles: ["Accounts User"] } };
		expect(routeWith(user, standard)("details")).toBeNull();
		expect(routeWith(user, { name: "Task Note", custom: 1 })("details")).toBeNull();
	});

	it("gives nothing without the right, without the meta, or on the index, which serves no editor", () => {
		expect(routeWith({ ...appBoot, session: { roles: ["Sales User"] } }, standard)("details")).toBeNull();
		expect(routeWith(appBoot, null)("details")).toBeNull();
		expect(routeWith(appBoot, standard, INDEX)("details")).toBeNull();
	});
});
