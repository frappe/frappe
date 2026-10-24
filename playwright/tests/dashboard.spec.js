import { test, expect } from "../support";

const ISLAND = "frappe.playwright_dashboard_fixture";

// Reports the title and actions its props name, as a page island does.
const FIXTURE_MODULE = `
	export function mount(el, { props }) {
		el.append(Object.assign(document.createElement("div"), { className: "fixture-dashboard" }));
		if (props.title) props.onTitle(props.title);
		if (props.actions) props.onActions(props.actions);
		return { update() {}, unmount() { el.replaceChildren(); } };
	}
`;

async function register_fixture(page) {
	await page.evaluate(
		([island, module]) => {
			const url = URL.createObjectURL(new Blob([module], { type: "text/javascript" }));
			frappe.boot.assets_json[`${island}.island.js`] = url;
			frappe.boot.ui_islands = [...(frappe.boot.ui_islands || []), island];
		},
		[ISLAND, FIXTURE_MODULE]
	);
}

// The server's `__onload` is faked, so the page draws an island on a site without the app that claims.
async function claim(page, doctype, island) {
	await page.route(
		(url) =>
			url.pathname.endsWith("/frappe.desk.form.load.getdoc") &&
			url.searchParams.get("doctype") === doctype,
		async (route) => {
			const response = await route.fetch();
			const json = await response.json();
			json.docs[0].__onload = { island };
			await route.fulfill({ response, json });
		}
	);
}

async function open_claimed_dashboard(page, desk, api, props) {
	const dashboard = "TODO-ISLAND-DASHBOARD";
	await page.goto("/desk");
	await desk.ready();
	await api.insert_doc(
		"Dashboard",
		{ name: dashboard, dashboard_name: dashboard, is_standard: 0 },
		true
	);
	await register_fixture(page);
	await claim(page, "Dashboard", { name: ISLAND, props });
	await page.evaluate((name) => frappe.set_route("dashboard-view", name), dashboard);
	await expect(page.locator(".dashboard-view-island .fixture-dashboard")).toBeAttached();
	return dashboard;
}

test.describe("Dashboard view", () => {
	test("should load", async ({ page, desk, api }) => {
		const chart = "TODO-YEARLY-TRENDS";
		const dashboard = "TODO-TEST-DASHBOARD";

		await page.goto("/desk");
		await desk.ready();

		await api.insert_doc(
			"Dashboard Chart",
			{
				is_standard: 0,
				chart_name: chart,
				chart_type: "Count",
				document_type: "ToDo",
				parent_document_type: "",
				based_on: "creation",
				group_by_type: "Count",
				timespan: "Last Year",
				time_interval: "Yearly",
				timeseries: 1,
				type: "Line",
				filters_json: "[]",
			},
			true
		);

		await api.insert_doc(
			"Dashboard",
			{
				name: dashboard,
				dashboard_name: dashboard,
				is_standard: 0,
				charts: [{ chart: chart }],
			},
			true
		);

		await page.goto(`/desk/dashboard-view/${dashboard}`);

		await expect(page.getByText(chart, { exact: true })).toBeVisible();
	});

	test("a dashboard the reader can see nothing on says so", async ({ page, desk, api }) => {
		const dashboard = "TODO-TEST-DASHBOARD";
		await page.goto("/desk");
		await desk.ready();
		await api.insert_doc(
			"Dashboard Chart",
			{
				is_standard: 0,
				chart_name: "TODO-YEARLY-TRENDS",
				chart_type: "Count",
				document_type: "ToDo",
				based_on: "creation",
				timespan: "Last Year",
				time_interval: "Yearly",
				timeseries: 1,
				type: "Line",
				filters_json: "[]",
			},
			true
		);
		await api.insert_doc(
			"Dashboard",
			{
				name: dashboard,
				dashboard_name: dashboard,
				is_standard: 0,
				charts: [{ chart: "TODO-YEARLY-TRENDS" }],
			},
			true
		);
		await page.route(
			"**/api/method/frappe.desk.doctype.dashboard.dashboard.get_permitted_*",
			(route) => route.fulfill({ json: { message: [] } })
		);

		await page.evaluate((name) => frappe.set_route("dashboard-view", name), dashboard);

		await expect(
			page.getByText("You don't have access to anything on this dashboard")
		).toBeVisible();
	});

	test("a dashboard the reader cannot open clears the one drawn before", async ({
		page,
		desk,
		api,
	}) => {
		const dashboard = "TODO-CLEAR-DASHBOARD";

		await page.goto("/desk");
		await desk.ready();
		await api.insert_doc(
			"Dashboard",
			{ name: dashboard, dashboard_name: dashboard, is_standard: 0 },
			true
		);
		await page.goto(`/desk/dashboard-view/${dashboard}`);
		await expect(page.locator(".dashboard-graph")).toBeAttached();

		await page.route("**/api/method/frappe.desk.form.load.getdoc?*", (route) =>
			route.fulfill({ status: 403, json: { exc_type: "PermissionError" } })
		);
		await page.evaluate(() => frappe.set_route("dashboard-view", "Not Permitted Dashboard"));

		await expect(page.locator(".dashboard-graph")).toHaveCount(0);
	});
});

test.describe("Dashboard view island", () => {
	test("an island that reports no title keeps the dashboard's name in the breadcrumb", async ({
		page,
		desk,
		api,
	}) => {
		const dashboard = await open_claimed_dashboard(page, desk, api, {});

		await expect(page.locator(".navbar-breadcrumbs:visible li:last-child")).toHaveText(
			dashboard
		);
	});

	test("an island's action labels print as text in the page menu", async ({
		page,
		desk,
		api,
	}) => {
		const label = "<b>Export</b>";
		await open_claimed_dashboard(page, desk, api, { actions: [{ label, href: "/" }] });

		await page.locator("#page-dashboard-view .menu-btn-group > button").click();
		const menu = page.locator("#page-dashboard-view .menu-btn-group .dropdown-menu");
		await expect(menu).toContainText(label);
		await expect(menu.locator("b")).toHaveCount(0);
	});

	test("a number card an app claims draws its island", async ({ page, desk, api }) => {
		const card = "TODO-ISLAND-CARD";
		const dashboard = "TODO-ISLAND-CARD-DASHBOARD";
		await page.goto("/desk");
		await desk.ready();
		await api.insert_doc(
			"Number Card",
			{
				name: card,
				label: card,
				is_standard: 0,
				type: "Document Type",
				document_type: "ToDo",
				function: "Count",
				filters_json: "[]",
			},
			true
		);
		await api.insert_doc(
			"Dashboard",
			{ name: dashboard, dashboard_name: dashboard, is_standard: 0, cards: [{ card }] },
			true
		);
		await register_fixture(page);
		await claim(page, "Number Card", { name: ISLAND, props: {} });

		await page.evaluate((name) => frappe.set_route("dashboard-view", name), dashboard);

		const widget = page.locator(".number-widget-box", { hasText: card });
		await expect(widget.locator(".number-card-island .fixture-dashboard")).toBeAttached();
		await expect(widget).toHaveClass(/number-widget-island/);
	});
});
