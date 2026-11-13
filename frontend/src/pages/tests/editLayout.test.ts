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

import { canEditLayout, useEditLayoutRoute } from "../editLayout";

const manager = { roles: ["System Manager"], developerMode: false };
const standard = { name: "Sales Invoice" };

describe("canEditLayout", () => {
	it("lets a System Manager customize a standard DocType outside developer mode", () => {
		expect(canEditLayout(standard, manager)).toBe(true);
	});

	it("lets a System Manager design a custom DocType", () => {
		expect(canEditLayout({ name: "Task Note", custom: 1 }, manager)).toBe(true);
	});

	it("keeps a standard Single shut outside developer mode, and opens it to Design in it", () => {
		const single = { name: "Print Settings", issingle: 1 };
		expect(canEditLayout(single, manager)).toBe(false);
		expect(canEditLayout(single, { ...manager, developerMode: true })).toBe(true);
	});

	it("refuses anyone without the System Manager role, developer mode or not", () => {
		const user = { roles: ["Accounts User"], developerMode: true };
		expect(canEditLayout(standard, user)).toBe(false);
		expect(canEditLayout({ name: "Task Note", custom: 1 }, user)).toBe(false);
	});
});

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
		expect(route("details", "FL-0002")).toMatchObject({ query: { layout: "details", row: "FL-0002" } });
	});

	it("gives nothing without the right, without the meta, or on the index, which serves no editor", () => {
		expect(routeWith({ ...appBoot, session: { roles: ["Sales User"] } }, standard)("details")).toBeNull();
		expect(routeWith(appBoot, null)("details")).toBeNull();
		expect(routeWith(appBoot, standard, INDEX)("details")).toBeNull();
	});
});
