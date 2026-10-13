import { test, expect } from "../support";
import target_doctype from "../fixtures/layout_target_doctype";

const TARGET = target_doctype.name;
const SLUG = TARGET.toLowerCase().replace(/ /g, "-");

test.describe("DocType Layout", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.insert_doc("DocType", target_doctype, true);

		await admin.remove_doc("DocType Layout", "Compact", true);
		await admin.remove_doc("DocType Layout", "Special", true);
		await admin.remove_doc("DocType Layout", "Todo Layout", true);

		await admin.insert_doc("DocType Layout", {
			title: "Compact",
			document_type: TARGET,
			fields: [
				{ fieldname: "data1", label: "Compact Data 1" },
				{ fieldname: "data2", hidden: 1 },
				{ fieldname: "is_special" },
			],
		});

		await admin.insert_doc("DocType Layout", {
			title: "Special",
			document_type: TARGET,
			condition: "doc.is_special == 1",
			fields: [
				{ fieldname: "data1" },
				{ fieldname: "data2" },
				{ fieldname: "is_special" },
				{ fieldname: "description", label: "Special Notes" },
			],
		});

		await admin.insert_doc("DocType Layout", {
			title: "Todo Layout",
			document_type: "ToDo",
			fields: [{ fieldname: "description", label: "Todo Notes" }],
		});
	});

	test.afterAll(async ({ admin }) => {
		await admin.remove_doc("DocType Layout", "Compact", true);
		await admin.remove_doc("DocType Layout", "Special", true);
		await admin.remove_doc("DocType Layout", "Todo Layout", true);
	});

	test.beforeEach(async ({ desk }) => {
		await desk.login("Administrator");
	});

	test("DocType Layout form: Sync Fields populates rows and Form Builder renders", async ({
		page,
		desk,
	}) => {
		await page.goto("/desk/doctype-layout/Compact");
		await expect(page.locator("body")).toHaveAttribute("data-ajax-state", "complete");

		const fieldnames = () =>
			page.evaluate(() => (cur_frm?.doc?.fields || []).map((row) => row.fieldname));
		await expect
			.poll(fieldnames)
			.toEqual(expect.arrayContaining(["data1", "data2", "is_special"]));
		expect(await fieldnames()).not.toContain("description");

		await page.getByRole("button", { name: "Sync Fields", exact: true }).click();
		await expect(page.locator(".modal:visible")).toContainText("Synced Fields");
		await desk.hide_dialog();

		await expect(page.locator('[data-testid="page-status"]:visible')).toContainText(
			"Not Saved"
		);

		await page.getByRole("tab", { name: "Parent Layout", exact: true }).click();
		await expect(page.locator(".form-builder-container")).toBeAttached();
	});

	test("Form Builder re-renders when switching layout records without a reload", async ({
		page,
	}) => {
		const form_builder = page.locator(".form-builder-container");
		const parent_layout_tab = page.getByRole("tab", { name: "Parent Layout", exact: true });
		const open_layout = async (name) => {
			await page.evaluate((name) => frappe.set_route("Form", "DocType Layout", name), name);
			await expect.poll(() => page.evaluate(() => cur_frm.doc.name)).toBe(name);
			await expect(page.locator("body")).toHaveAttribute("data-ajax-state", "complete");
			await parent_layout_tab.click();
		};

		await page.goto("/desk/doctype-layout/Compact");
		await expect(page.locator("body")).toHaveAttribute("data-ajax-state", "complete");
		await parent_layout_tab.click();
		await expect(form_builder).toContainText("Compact Data 1");

		await open_layout("Special");
		await expect(form_builder).toContainText("Special Notes");
		await expect(form_builder).not.toContainText("Compact Data 1");

		await open_layout("Todo Layout");
		await expect(form_builder).toContainText("Todo Notes");
		await expect(form_builder).not.toContainText("Special Notes");

		await open_layout("Compact");
		await expect(form_builder).toContainText("Compact Data 1");
		await expect(form_builder).not.toContainText("Todo Notes");
	});

	test("Condition auto-switches the layout after a matching value is saved", async ({
		page,
		desk,
	}) => {
		await page.goto(`/desk/${SLUG}/new`);
		await expect(page.locator("body")).toHaveAttribute("data-ajax-state", "complete");

		await expect(page).not.toHaveURL(/layout=/);

		await desk.fill_field("data1", "auto-switch", "Data");
		await page.locator("[data-fieldname='is_special'] label").click();
		await expect
			.poll(() => page.evaluate(() => [cur_frm.doc.data1, cur_frm.doc.is_special]))
			.toEqual(["auto-switch", 1]);
		await desk.click_primary_button("Save");

		await expect(page.locator(".navbar-breadcrumbs:visible")).toContainText("Special");
		await expect(page).toHaveURL((url) => url.search.includes("layout=Special"));
		await expect(
			page.locator(".page-container:visible [data-fieldname='description'] .clearfix label")
		).toContainText("Special Notes");
	});
});
