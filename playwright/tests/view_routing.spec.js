import { test, expect, TEST_USER } from "../support";

const pathname = (page) => new URL(page.url()).pathname;

async function expect_list_view(page, view_name) {
	await expect.poll(() => page.evaluate(() => window.cur_list?.view_name)).toBe(view_name);
}

function setup_default_view(api, args) {
	return api.call("frappe.tests.ui_test_helpers.setup_default_view", args);
}

function list_loaded(page) {
	return page.waitForResponse(
		(res) =>
			res.request().method() === "POST" &&
			res.url().includes("/api/method/frappe.desk.reportview.get")
	);
}

test.describe("View", () => {
	test.afterAll(async ({ admin }) => {
		await admin.remove_doc("Property Setter", "Event-main-default_view", true);
		await admin.remove_doc(
			"Property Setter",
			"Event-main-force_re_route_to_default_view",
			true
		);
		await admin.update_doc("User", TEST_USER, { user_emails: [] });
		await admin.remove_doc("Email Account", "Email Linking", true);
	});

	test("Route to ToDo List View", async ({ page, desk }) => {
		await page.goto("/desk/todo/view/list");
		await desk.ready();
		await expect_list_view(page, "List");
	});

	test("Route to ToDo Report View", async ({ page, desk }) => {
		await page.goto("/desk/todo/view/report");
		await desk.ready();
		await expect_list_view(page, "Report");
	});

	test("Route to ToDo Dashboard View", async ({ page, desk }) => {
		await page.goto("/desk/todo/view/dashboard");
		await desk.ready();
		await expect_list_view(page, "Dashboard");
	});

	test("Route to ToDo Gantt View", async ({ page, desk }) => {
		await page.goto("/desk/todo/view/gantt");
		await desk.ready();
		await expect_list_view(page, "Gantt");
	});

	test("Route to ToDo Kanban View", async ({ page, desk, api }) => {
		await api.call("frappe.tests.ui_test_helpers.create_kanban");
		await page.goto("/desk/note/view/kanban/_Note _Kanban");
		await desk.ready();
		await expect_list_view(page, "Kanban");
	});

	test("Route to ToDo Calendar View", async ({ page, desk }) => {
		await page.goto("/desk/todo/view/calendar");
		await desk.ready();
		await expect_list_view(page, "Calendar");
	});

	test("Route to Custom Tree View", async ({ page, desk, api }) => {
		await api.call("frappe.tests.ui_test_helpers.setup_tree_doctype");
		await page.goto("/desk/custom-tree/view/tree");
		await desk.ready();
		await expect.poll(() => page.evaluate(() => window.cur_tree?.view_name)).toBe("Tree");
	});

	test("Route to Custom Image View", async ({ page, desk, api }) => {
		await api.call("frappe.tests.ui_test_helpers.setup_image_doctype");
		await page.goto("/app/custom-image/view/image");
		await desk.ready();
		await expect_list_view(page, "Image");
	});

	test("Route to Communication Inbox View", async ({ page, desk, api }) => {
		await api.call("frappe.tests.ui_test_helpers.setup_inbox");
		await page.goto("/app/communication/view/inbox");
		await desk.ready();
		await expect_list_view(page, "Inbox");
	});

	test("Route to File View", async ({ page }) => {
		let loaded = list_loaded(page);
		await page.goto("/app/file");
		await loaded;
		await expect_list_view(page, "File");
		await expect.poll(() => page.evaluate(() => cur_list.current_folder)).toBe("Home");

		loaded = list_loaded(page);
		await page.goto("/app/file/view/home/Attachments");
		await loaded;
		await expect_list_view(page, "File");
		await expect
			.poll(() => page.evaluate(() => cur_list.current_folder))
			.toBe("Home/Attachments");
	});

	test("Re-route to default view", async ({ page, desk, api }) => {
		await setup_default_view(api, { view: "Report" });
		await page.goto("/app/event");
		await desk.ready();
		await expect_list_view(page, "Report");
	});

	test("Route to default view from app/{doctype}", async ({ page, desk, api }) => {
		await setup_default_view(api, { view: "Report" });
		await page.goto("/desk/event");
		await desk.ready();
		await expect_list_view(page, "Report");
	});

	test("Route to default view from app/{doctype}/view", async ({ page, desk, api }) => {
		await setup_default_view(api, { view: "Report" });
		await page.goto("/desk/event/view");
		await desk.ready();
		await expect_list_view(page, "Report");
	});

	test("Force Route to default view from app/{doctype}", async ({ page, desk, api }) => {
		await setup_default_view(api, { view: "Report", force_reroute: true });
		await page.goto("/desk/event");
		await desk.ready();
		await expect_list_view(page, "Report");
	});

	test("Force Route to default view from app/{doctype}/view", async ({ page, desk, api }) => {
		await setup_default_view(api, { view: "Report", force_reroute: true });
		await page.goto("/desk/event/view");
		await desk.ready();
		await expect_list_view(page, "Report");
	});

	test("Force Route to default view from app/{doctype}/view/list", async ({
		page,
		desk,
		api,
	}) => {
		await setup_default_view(api, { view: "Report", force_reroute: true });
		await page.goto("/desk/event/view/list");
		await desk.ready();
		await expect_list_view(page, "Report");
	});

	test("Validate Route History for Default View", async ({ page, api }) => {
		await setup_default_view(api, { view: "Report" });
		await page.goto("/desk/event");
		await page.goto("/desk/event/view/list");
		await expect.poll(() => pathname(page)).toMatch(/\/event\/view\/list$/);
		await page.goBack();
		await expect.poll(() => pathname(page)).toMatch(/\/event$/);
	});

	test("Route to Form", async ({ page }) => {
		await page.goto(`/desk/user/${TEST_USER}`);
		await expect.poll(() => page.evaluate(() => window.cur_frm?.doc.name)).toBe(TEST_USER);
	});

	test("Route to Website Workspace", async ({ page }) => {
		await page.goto("/desk/website");
		await expect(page.locator(".navbar-breadcrumbs:visible li:last-child")).toContainText(
			"Website"
		);
	});
});
