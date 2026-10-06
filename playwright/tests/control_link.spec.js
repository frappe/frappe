import { test, expect, TEST_USER } from "../support";
import { shown_dialog } from "../support/shown_dialog";

test.describe("Control Link", () => {
	// Two tests find the ToDo by typing into a Link field and assert the field picked the record
	// they just made, so every test gets its own description. Only the stamp is typed: the
	// field searches the whole description.
	let todo_stamp;
	let todo_description;
	let todo;
	let created_todos = [];

	test.beforeEach(async ({ page, desk, api }) => {
		created_todos = [];
		todo_stamp = String(Date.now());
		todo_description = `this is a test todo for link ${todo_stamp}`;
		[todo] = await api.create_records({
			doctype: "ToDo",
			description: todo_description,
		});
		created_todos.push(todo);
		await page.goto("/desk/website");
		await desk.ready();
	});

	test.afterEach(async ({ admin }) => {
		for (const name of created_todos) {
			await admin.remove_doc("ToDo", name, true);
		}
	});

	test.afterAll(async ({ admin }) => {
		await admin.set_value("User", TEST_USER, { language: "en" });
		await admin.remove_doc("Property Setter", "ToDo-main-show_title_field_in_link", true);
		await admin.remove_doc("Property Setter", "ToDo-assigned_by-default", true);
	});

	async function get_dialog_with_link(desk) {
		return desk.dialog({
			title: "Link",
			fields: [
				{
					label: "Select ToDo",
					fieldname: "link",
					fieldtype: "Link",
					options: "ToDo",
				},
			],
		});
	}

	async function get_dialog_with_gender_link(desk) {
		return desk.dialog({
			title: "Link",
			fields: [
				{
					label: "Select Gender",
					fieldname: "link",
					fieldtype: "Link",
					options: "Gender",
				},
			],
		});
	}

	const get_dropdown = (input) => input.locator("xpath=..").getByRole("listbox");

	async function focus_link_input(page) {
		const input = page.locator(".frappe-control[data-fieldname=link] input");
		await input.focus();
		await expect(get_dropdown(input)).toBeVisible();
		return input;
	}

	async function select_first_result(input, text) {
		await input.pressSequentially(text, { delay: 100 });
		await expect(get_dropdown(input).locator("div[role='option']").first()).toContainText(
			text
		);
		await input.press("Enter");
	}

	const get_link_value_and_label = (dialog) =>
		dialog.evaluate((d) => {
			const field = d.get_field("link");
			return { value: field.get_value(), label: field.get_label_value() };
		});

	const wait_for_link_validation = (page) =>
		page.waitForResponse((res) =>
			res.url().includes("/api/method/frappe.client.validate_link_and_fetch")
		);

	async function clear_cache(page, desk) {
		const reloaded = page.waitForEvent("load");
		await desk.clear_cache();
		await reloaded;
		await desk.ready();
	}

	const get_full_name = async (api) => {
		const r = await api.call("frappe.client.get_value", {
			doctype: "User",
			filters: {
				name: TEST_USER,
			},
			fieldname: "full_name",
		});
		return r.message.full_name;
	};

	test("should set the valid value", async ({ page, desk, api }) => {
		const dialog = await get_dialog_with_link(desk);

		await api.insert_doc(
			"Property Setter",
			{
				doctype: "Property Setter",
				doc_type: "ToDo",
				property: "show_title_field_in_link",
				property_type: "Check",
				doctype_or_field: "DocType",
				value: "0",
			},
			true
		);

		const input = await focus_link_input(page);
		await select_first_result(input, todo_stamp);
		await input.blur();
		await expect.poll(() => dialog.evaluate((d) => d.get_value("link"))).toBe(todo);
	});

	test("should unset invalid value", async ({ page, desk }) => {
		await get_dialog_with_link(desk);

		const validated = wait_for_link_validation(page);
		const input = await focus_link_input(page);
		await input.pressSequentially("invalid value", { delay: 100 });
		await input.blur();
		await validated;
		await expect(input).toHaveValue("");
	});

	test("should be possible set empty value explicitly", async ({ page, desk }) => {
		await get_dialog_with_link(desk);

		const validated = wait_for_link_validation(page);
		const input = await focus_link_input(page);
		await input.pressSequentially("  ", { delay: 100 });
		await input.blur();
		await validated;
		await expect(input).toHaveValue("");
		expect(await page.evaluate(() => cur_dialog.get_value("link"))).toBe("");
	});

	test("should show open link button", async ({ page, desk }) => {
		await get_dialog_with_link(desk);

		const input = await focus_link_input(page);
		await input.pressSequentially(todo, { delay: 100 });
		await input.blur();

		const open_button = page.locator(".frappe-control[data-fieldname=link] .btn-open");
		// the buttons are hidden again 250ms after the blur, so hover until they stay
		await expect(async () => {
			await page.mouse.move(0, 0);
			await input.hover();
			await expect(open_button).toBeVisible({ timeout: 1000 });
		}).toPass();
		await expect(open_button).toHaveAttribute("href", `/desk/todo/${todo}`);
	});

	test("show title field in link", async ({ page, desk, api }) => {
		await api.insert_doc(
			"Property Setter",
			{
				doctype: "Property Setter",
				doc_type: "ToDo",
				property: "show_title_field_in_link",
				property_type: "Check",
				doctype_or_field: "DocType",
				value: "1",
			},
			true
		);

		await page.reload();
		await desk.ready();

		const dialog = await get_dialog_with_link(desk);
		await page.evaluate(() => {
			frappe.boot.link_title_doctypes = ["ToDo"];
		});

		const input = await focus_link_input(page);
		await select_first_result(input, todo_stamp);
		// a blur while the selection is still being validated leaves the title as the value
		await expect.poll(() => dialog.evaluate((d) => d.get_value("link"))).toBe(todo);
		await input.blur();
		await expect
			.poll(() => get_link_value_and_label(dialog))
			.toEqual({ value: todo, label: todo_description });
	});

	test("should update dependant fields (via fetch_from)", async ({ page, desk, api }) => {
		await page.goto(`/desk/todo/${todo}`);
		const full_name = page.locator(
			".frappe-control[data-fieldname=assigned_by_full_name] .control-value"
		);
		const get_assigned_by = () => page.evaluate(() => cur_frm.doc.assigned_by);

		const input = await desk.fill_field("assigned_by", TEST_USER, "Link");
		await expect(full_name).toContainText(await get_full_name(api));
		await expect.poll(get_assigned_by).toBe(TEST_USER);

		await input.clear();
		await input.pressSequentially("invalid input", { delay: 100 });
		await input.blur();
		await expect(full_name).toContainText("");
		await expect.poll(get_assigned_by).toBe(undefined);

		await input.clear();
		await input.focus();
		await expect(get_dropdown(input)).toBeVisible();
		const validated = wait_for_link_validation(page);
		await input.pressSequentially(TEST_USER, { delay: 100 });
		await input.blur();
		await validated;
		await expect.poll(get_assigned_by).toBe(TEST_USER);

		await input.clear();
		await input.blur();
		await expect(full_name).toContainText("");
		await expect.poll(get_assigned_by).toBe("");
	});

	test("should set default values", async ({ page, desk, api }) => {
		await api.insert_doc(
			"Property Setter",
			{
				doctype_or_field: "DocField",
				doc_type: "ToDo",
				field_name: "assigned_by",
				property: "default",
				property_type: "Text",
				value: TEST_USER,
			},
			true
		);
		await page.reload();
		await desk.new_form("ToDo");
		const description = await desk.fill_field("description", "new", "Text Editor");
		await description.blur();
		await expect.poll(() => page.evaluate(() => cur_frm.doc.description)).toContain("new");
		const saved = await (await desk.save()).json();
		created_todos.push(saved.docs[0].name);
		const full_name = page.locator(
			".frappe-control[data-fieldname=assigned_by_full_name] .control-value"
		);
		await expect(full_name).toContainText(await get_full_name(api));

		// if user clears default value explicitly, system should not reset default again
		const assigned_by = desk.get_field("assigned_by");
		await assigned_by.clear();
		await assigned_by.blur();
		await expect.poll(() => page.evaluate(() => cur_frm.doc.assigned_by)).toBe("");
		await desk.save();
		await expect(assigned_by).toHaveValue("");
		await expect(full_name).toContainText("");
	});

	test("show translated text for Gender link field with language de with input in de", async ({
		page,
		desk,
		api,
	}) => {
		await api.call("frappe.tests.ui_test_helpers.insert_translations");
		await api.set_value("User", TEST_USER, { language: "de" });
		await clear_cache(page, desk);

		const dialog = await get_dialog_with_gender_link(desk);

		const input = await focus_link_input(page);
		await select_first_result(input, "Sonstiges");
		await input.blur();
		await expect
			.poll(() => get_link_value_and_label(dialog))
			.toEqual({ value: "Other", label: "Sonstiges" });
	});

	test("show text for Gender link field with language en", async ({ page, desk, api }) => {
		await api.set_value("User", TEST_USER, { language: "en" });
		await clear_cache(page, desk);

		const dialog = await get_dialog_with_gender_link(desk);

		const input = await focus_link_input(page);
		await select_first_result(input, "Non-Conforming");
		await input.blur();
		await expect
			.poll(() => get_link_value_and_label(dialog))
			.toEqual({ value: "Non-Conforming", label: "Non-Conforming" });
	});

	test("show custom link option", async ({ page, desk }) => {
		await page.evaluate(() => {
			frappe.ui.form.ControlLink.link_options = () => {
				return [
					{
						html:
							"<span class='text-primary custom-link-option'>" +
							frappe.utils.icon("search", "xs", "", "margin-right: 5px;") +
							" Custom Link Option" +
							"</span>",
						label: "Custom Link Option",
						value: "custom__link_option",
						action: () => {},
					},
				];
			};
		});

		await get_dialog_with_link(desk);
		const input = page.locator(".frappe-control[data-fieldname=link] input");
		await input.focus();
		await input.pressSequentially("custom", { delay: 100 });
		await expect(page.locator(".custom-link-option")).toBeVisible();
	});

	test("keeps list format filters when merging link filters", async ({ page }) => {
		const dialog = await page.evaluateHandle(() => {
			const dialog = new frappe.ui.Dialog({
				title: "Link",
				fields: [
					{
						label: "Select ToDo",
						fieldname: "link",
						fieldtype: "Link",
						options: "ToDo",
						link_filters: '[["ToDo", "status", "=", "Closed"]]',
						get_query: () => ({
							filters: [
								["ToDo", "status", "=", "Open"],
								["ToDo", "priority", "=", "High"],
								["Communication", "status", "=", "Open"],
								["description", "like", "%test todo%"],
							],
						}),
					},
				],
			});
			dialog.show();
			return dialog;
		});
		await shown_dialog(dialog);

		const filters = await dialog.evaluate(
			(d) => d.get_field("link").get_search_args("").filters
		);
		expect(filters).toEqual([
			["ToDo", "priority", "=", "High"],
			["Communication", "status", "=", "Open"],
			["description", "like", "%test todo%"],
			["status", "=", "Closed"],
		]);
	});
});
