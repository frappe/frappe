// A saved view's address: the list waits for the view, opens with its label, and a view the
// person cannot see shows one not-found page, never the plain list.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, type App } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";

const retitle = vi.hoisted(() => vi.fn());

vi.mock("@/shell/PageFrame.vue", async () => {
	const { defineComponent, h } = await import("vue");
	const PageState = (await import("@/shell/PageState.vue")).default;
	return {
		default: defineComponent({
			props: ["state"],
			setup: (props) => () => h("div", { "data-frame": "" }, props.state ? h(PageState, props.state) : []),
		}),
		pageGutter: "",
	};
});
vi.mock("@/pages/list/DoctypeList.vue", async () => {
	const { defineComponent, h } = await import("vue");
	return {
		default: defineComponent({
			props: ["doctype", "view", "viewLabel"],
			setup: (props) => () => h("div", { "data-list": props.viewLabel ?? "" }),
		}),
	};
});
vi.mock("@/shell/recentVisits", () => ({ recentVisits: { retitle } }));
vi.mock("@/router/routeFor", () => ({
	routeFor: (doctype: string) => ({ name: "list", params: { doctype: doctype.toLowerCase() } }),
}));

import List from "../../List.vue";

const apps: App[] = [];

afterEach(() => {
	for (const app of apps.splice(0)) app.unmount();
	document.body.innerHTML = "";
	vi.unstubAllGlobals();
	retitle.mockReset();
});

function answer(status: number, body: unknown) {
	let send!: () => void;
	const asked: string[] = [];
	vi.stubGlobal("fetch", (url: string) => {
		asked.push(String(url));
		return new Promise<Response>((resolve) => {
			send = () => resolve(new Response(JSON.stringify(body), { status }));
		});
	});
	return { asked, send: async () => (send(), await flush()) };
}

async function flush() {
	for (let i = 0; i < 5; i++) await new Promise((resolve) => setTimeout(resolve));
}

async function mount(path: string) {
	const router = createRouter({
		history: createMemoryHistory("/apps/desk"),
		routes: [
			{ path: "/", name: "home", component: { render: () => null } },
			{ path: "/:doctype", name: "list", component: { render: () => null } },
			{ path: "/:doctype/view/:key", name: "saved-view", component: { render: () => null } },
		],
	});
	await router.push(path);
	const root = document.createElement("div");
	document.body.appendChild(root);
	const app = createApp(defineComponent({ render: () => h(List) }));
	app.use(router).provide("boot", { app: "desk", app_title: "Desk" }).provide("addresses", {
		moduleName: () => null,
		doctypeOf: () => "ToDo",
		slugOf: () => "todo",
	});
	app.mount(root);
	apps.push(app);
	await nextTick();
	return {
		list: () => root.querySelector<HTMLElement>("[data-list]"),
		state: () => root.querySelector<HTMLElement>("[data-page-state]")?.dataset.pageState,
		text: () => root.textContent ?? "",
		action: () => root.querySelector<HTMLAnchorElement>("[data-page-state] a"),
		listHref: router.resolve({ name: "list", params: { doctype: "todo" } }).href,
	};
}

describe("a saved view's address", () => {
	it("draws no list until the view is found, then the list with the view's label", async () => {
		const server = answer(200, { data: { key: "open", label: "Open todos", type: "List" } });
		const page = await mount("/todo/view/open");

		expect(page.list()).toBeNull();
		expect(server.asked[0]).toContain("frappe.desk.doctype.doctype_view.api.find");
		expect(server.asked[0]).toContain("key=open");

		await server.send();
		expect(page.list()?.dataset.list).toBe("Open todos");
		expect(retitle).toHaveBeenCalledWith("/todo/view/open", "Open todos");
	});

	it("draws the view not found page, never the plain list, when the view is missing", async () => {
		const server = answer(404, { errors: [{ type: "DoesNotExistError", message: "This view doesn't exist." }] });
		const page = await mount("/todo/view/gone");
		await server.send();

		expect(page.state()).toBe("viewNotFound");
		expect(page.list()).toBeNull();
		expect(page.text()).toContain("This view doesn't exist");
		expect(page.action()?.getAttribute("href")).toBe(page.listHref);
	});

	it("asks nothing for the plain list", async () => {
		const server = answer(200, {});
		const page = await mount("/todo");

		expect(server.asked).toEqual([]);
		expect(page.list()?.dataset.list).toBe("");
	});
});
