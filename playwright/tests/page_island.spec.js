import { test, expect } from "../support";

const PAGE = "playwright-island-page";
const ISLAND = `frappe.page.${PAGE}`;
const GETPAGE = "/api/method/frappe.desk.desk_page.getpage";

const FIXTURE_MODULE = `
	export function mount(el, context) {
		const node = document.createElement("div");
		node.className = "page-island-fixture";
		el.appendChild(node);

		let props = { ...(context.props || {}) };
		const render = () => (node.textContent = (props.route || []).join("/"));
		render();

		props.onTitle?.("Reported Title");
		props.onActions?.([{ label: "Reported Action", onClick: () => (window.__action_ran = true) }]);

		return Promise.resolve({
			update(next) {
				props = { ...props, ...next };
				render();
			},
			unmount() {
				node.remove();
			},
		});
	}
`;

function page_doc() {
	return {
		docs: [
			{
				doctype: "Page",
				name: PAGE,
				page_name: PAGE,
				title: "Page Title",
				module: "Desk",
				standard: "Yes",
				type: "Frappe UI",
				island: ISLAND,
				script: "",
				style: "",
				content: null,
			},
		],
	};
}

async function visit_page(page, desk, { build = true, route = [] } = {}) {
	await page.goto("/app/website");
	await desk.ready();

	const getpage = page.waitForResponse((res) => res.url().includes(GETPAGE));
	await page.evaluate(
		([page_name, island, module, build, route]) => {
			localStorage.removeItem(`_page:${page_name}`);
			if (build) {
				frappe.boot.assets_json[`${island}.island.js`] = URL.createObjectURL(
					new Blob([module], { type: "text/javascript" })
				);
			}
			frappe.boot.ui_islands = [...(frappe.boot.ui_islands || []), island];
			frappe.set_route(page_name, ...route);
		},
		[PAGE, ISLAND, FIXTURE_MODULE, build, route]
	);
	await getpage;
}

test.describe("Frappe UI page", () => {
	test.beforeEach(async ({ page }) => {
		await page.route(`**${GETPAGE}`, (route) => route.fulfill({ json: page_doc() }));
	});

	test("mounts the island the page names, inside the page content", async ({ page, desk }) => {
		await visit_page(page, desk);
		await expect(
			page.locator(`#page-${PAGE} .page-content .page-island-fixture`)
		).toBeAttached();
	});

	test("builds a page head, so the island draws no header of its own", async ({
		page,
		desk,
	}) => {
		await visit_page(page, desk);
		await expect(page.locator(`#page-${PAGE} .page-head`)).toBeAttached();
	});

	test("bounds the page, so the island scrolls its own body", async ({ page, desk }) => {
		await visit_page(page, desk);
		await expect(page.locator("body")).toHaveClass(/(^|\s)island-page(\s|$)/);
	});

	test("takes the page title from what the island reports", async ({ page, desk }) => {
		await visit_page(page, desk);
		await expect(page).toHaveTitle(/Reported Title/);
	});

	test("fills the page menu from the actions the island reports", async ({ page, desk }) => {
		await visit_page(page, desk);
		await page.locator(`#page-${PAGE} .menu-btn-group`).click();
		await expect(page.locator(`#page-${PAGE} .menu-btn-group .dropdown-menu`)).toContainText(
			"Reported Action"
		);
	});

	test("hands the island the route below the page", async ({ page, desk }) => {
		await visit_page(page, desk, { route: ["one", "two"] });
		await expect(page.locator(".page-island-fixture")).toHaveText("one/two");
	});

	test("updates the island in place when the route below the page moves", async ({
		page,
		desk,
	}) => {
		await visit_page(page, desk);
		await expect(page.locator(".page-island-fixture")).toHaveText("");
		await page.evaluate((page_name) => frappe.set_route(page_name, "later"), PAGE);
		await expect(page.locator(".page-island-fixture")).toHaveText("later");
	});

	test("says the page is unbuilt when its bundle is missing", async ({ page, desk }) => {
		await visit_page(page, desk, { build: false });
		await expect(page.locator(`#page-${PAGE} .page-content`)).toContainText(
			"has not been built"
		);
	});
});
