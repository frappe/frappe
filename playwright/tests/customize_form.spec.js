import { test, expect } from "../support";

test.describe("Customize Form", () => {
	test.afterAll(async ({ admin }) => {
		const { docs } = await admin.call("run_doc_method", {
			method: "fetch_to_customize",
			docs: JSON.stringify({
				doctype: "Customize Form",
				name: "Customize Form",
				doc_type: "Note",
			}),
		});
		await admin.call("run_doc_method", {
			method: "save_customization",
			docs: JSON.stringify({ ...docs[0], states: [] }),
		});
	});

	test("Changing to naming rule should update autoname", async ({ page, desk }) => {
		await page.goto("/desk/customize-form");
		await desk.ready();

		const doc_type = desk.get_field("doc_type", "Link");
		await doc_type.focus();
		await doc_type.pressSequentially("ToDo", { delay: 100 });
		await expect(
			page.locator('[data-fieldname="doc_type"] div[role="option"]').first()
		).toContainText("ToDo");
		await doc_type.press("Enter");
		await expect.poll(() => page.evaluate(() => cur_frm.doc.doc_type)).toBe("ToDo");
		await expect(page.getByRole("tab", { name: "Form", exact: true })).toHaveClass(/active/);
		await expect(page.locator(".form-builder-container")).toBeVisible();
		await page.getByRole("tab", { name: "Details", exact: true }).click();
		await desk.click_form_section("Naming");
		const naming_rule_default_autoname_map = {
			"Set by user": "prompt",
			"By fieldname": "field:",
			Expression: "",
			Random: "hash",
			"By script": "",
		};
		for (const [naming_rule, value] of Object.entries(naming_rule_default_autoname_map)) {
			await desk.fill_field("naming_rule", naming_rule, "Select");
			await expect(desk.get_field("autoname", "Data")).toHaveValue(value);
		}
	});

	test("saves a changed color on an existing document state", async ({ page, desk, api }) => {
		await page.goto("/desk/customize-form");
		await desk.ready();
		await desk.fill_field("doc_type", "Note", "Link");
		await expect(page.locator(".form-builder-container")).toBeVisible();
		await page.evaluate(() => {
			cur_frm.clear_table("states");
			cur_frm.add_child("states", { title: "Reviewed", color: "Blue" });
			return frappe.customize_form.save_customization(cur_frm);
		});

		await page.reload();
		await desk.ready();
		await expect(page.locator(".form-builder-container")).toBeVisible();
		await page.getByRole("tab", { name: "Details", exact: true }).click();
		await page
			.locator('.frappe-control[data-fieldname="states"] [data-idx="1"] .btn-open-row')
			.click();
		await desk.fill_table_field("states", "1", "color", "Green", "Select");
		await page.locator(".grid-row-open .grid-collapse-row").click();
		await desk.click_primary_button("Update");

		await expect
			.poll(async () => {
				const { message } = await api.call("frappe.client.get_value", {
					doctype: "DocType State",
					parent: "DocType",
					filters: { parent: "Note", title: "Reviewed" },
					fieldname: "color",
				});
				return message?.color;
			})
			.toBe("Green");
	});
});
