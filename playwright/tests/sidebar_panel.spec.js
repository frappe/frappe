import { test, expect, use_shared_page } from "../support";

const HIDDEN = /(^|\s)hidden(\s|$)/;

test.describe("Sidebar Panel", () => {
	const shared = use_shared_page();

	test.beforeAll(async () => {
		// Not /app: that is the apps screen, which hides the body sidebar, and with it the
		// container the panels mount in.
		await shared.page.goto("/app/todo");
		await shared.desk.ready();
	});

	test.beforeEach(async () => {
		await shared.page.evaluate(() => frappe.ui.sidebar_panels.close_all());
	});

	test("registers the notification panel", async () => {
		const { page } = shared;
		await expect
			.poll(() =>
				page.evaluate(() => Boolean(frappe.ui.sidebar_panels.panels.notifications))
			)
			.toBe(true);
	});

	test("mounts the panel beside the sidebar, not inside it", async () => {
		const { page } = shared;
		await expect(page.locator(".body-sidebar-container > .sidebar-panel")).not.toHaveCount(0);
		await expect(page.locator(".body-sidebar .sidebar-panel")).toHaveCount(0);
	});

	test("opens and closes on toggle", async () => {
		const { page } = shared;
		const panel = page.locator(".sidebar-panel-notifications");
		await expect(panel).toHaveClass(HIDDEN);
		await page.evaluate(() => frappe.ui.sidebar_panels.toggle("notifications"));
		await expect(panel).not.toHaveClass(HIDDEN);
		await page.evaluate(() => frappe.ui.sidebar_panels.toggle("notifications"));
		await expect(panel).toHaveClass(HIDDEN);
	});

	test("closes on Escape", async () => {
		const { page } = shared;
		const panel = page.locator(".sidebar-panel-notifications");
		await page.evaluate(() => frappe.ui.sidebar_panels.show("notifications"));
		await expect(panel).not.toHaveClass(HIDDEN);
		await page.keyboard.press("Escape");
		await expect(panel).toHaveClass(HIDDEN);
	});

	test("closes when clicked outside", async () => {
		const { page } = shared;
		const panel = page.locator(".sidebar-panel-notifications");
		await page.evaluate(() => frappe.ui.sidebar_panels.show("notifications"));
		await expect(panel).not.toHaveClass(HIDDEN);
		// Dispatched on body rather than clicking a page element: the centre of a workspace
		// is real content, and clicking it navigates, which takes the sidebar with it.
		await page.evaluate(() => document.body.click());
		await expect(panel).toHaveClass(HIDDEN);
	});

	test("stays open when clicked inside", async () => {
		const { page } = shared;
		const panel = page.locator(".sidebar-panel-notifications");
		await page.evaluate(() => frappe.ui.sidebar_panels.show("notifications"));
		await panel.locator(".panel-title").click();
		await expect(panel).not.toHaveClass(HIDDEN);
	});

	test("closes from the panel's own close button", async () => {
		const { page } = shared;
		const panel = page.locator(".sidebar-panel-notifications");
		await page.evaluate(() => frappe.ui.sidebar_panels.show("notifications"));
		await panel.locator(".panel-close").click();
		await expect(panel).toHaveClass(HIDDEN);
	});

	test("keeps aria-expanded on the trigger in step", async () => {
		const { page } = shared;
		const trigger = page.locator(".sidebar-notification").first();
		await expect(trigger).toHaveAttribute("aria-expanded", "false");
		await page.evaluate(() => frappe.ui.sidebar_panels.show("notifications"));
		await expect(trigger).toHaveAttribute("aria-expanded", "true");
		await page.evaluate(() => frappe.ui.sidebar_panels.close_all());
		await expect(trigger).toHaveAttribute("aria-expanded", "false");
	});

	test("only lets one panel be open", async () => {
		const { page } = shared;
		const notifications = page.locator(".sidebar-panel-notifications");
		await page.evaluate(() => {
			new frappe.ui.SidebarPanel({ name: "test-other", title: "Other" });
			frappe.ui.sidebar_panels.show("notifications");
		});
		await expect(notifications).not.toHaveClass(HIDDEN);

		await page.evaluate(() => frappe.ui.sidebar_panels.show("test-other"));
		await expect(page.locator(".sidebar-panel-test-other")).not.toHaveClass(HIDDEN);
		await expect(notifications).toHaveClass(HIDDEN);
	});

	test("closes on navigation", async () => {
		const { page } = shared;
		const panel = page.locator(".sidebar-panel-notifications");
		await page.evaluate(() => frappe.ui.sidebar_panels.show("notifications"));
		await expect(panel).not.toHaveClass(HIDDEN);
		// Routed rather than re-visited: a reload would rebuild the panel hidden and pass
		// without the page-change handler doing anything.
		await page.evaluate(() => {
			frappe.set_route("List", "Note");
		});
		await expect(panel).toHaveClass(HIDDEN);
	});

	test("carries both triggers on the sidebar, docked app or not", async () => {
		const { page } = shared;
		await expect(page.locator(".standard-items-band .sidebar-notification")).not.toHaveCount(
			0
		);
		await expect(page.locator(".dock .sidebar-notification")).toHaveCount(0);
	});

	test("opens from the sidebar bell", async () => {
		const { page } = shared;
		await page.locator(".standard-items-band .sidebar-notification").click();
		await expect(page.locator(".sidebar-panel-notifications")).not.toHaveClass(HIDDEN);
	});
});
