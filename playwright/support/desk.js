import { expect } from "@playwright/test";
import { ADMIN_PASSWORD, TEST_USER } from "./config";

const slug = (doctype) => doctype.toLowerCase().replace(/ /g, "-");
const escape_regex = (text) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

export class Desk {
	constructor(page, api) {
		this.page = page;
		this.api = api;
	}

	async login(email = TEST_USER, password = ADMIN_PASSWORD) {
		const res = await this.page.request.post("/api/method/login", {
			data: { usr: email, pwd: password },
		});
		expect(res.status(), `login as ${email}: ${await res.text()}`).toBe(200);
		this.api.token = null;
	}

	async logout() {
		await this.api.call("logout");
		this.api.token = null;
	}

	async ready() {
		await this.page.waitForFunction(
			() => window.frappe && frappe.app && frappe.request.ajax_count === 0
		);
		await expect(this.page.locator(".layout-main-section:visible > *").first()).toBeAttached();
	}

	async new_form(doctype) {
		const route = slug(doctype);
		const body = this.page.locator("body");
		await this.page.goto(`/desk/${route}/new`);
		await expect(body).toHaveAttribute(
			"data-route",
			new RegExp(`^Form/${escape_regex(doctype)}/new-${route}-`)
		);
		await expect(body).toHaveAttribute("data-ajax-state", "complete");
	}

	async go_to_list(doctype) {
		await this.page.goto(`/desk/${slug(doctype)}`);
	}

	clear_cache() {
		return this.page.evaluate(() => frappe.ui.toolbar.clear_cache());
	}

	get_field(fieldname, fieldtype = "Data") {
		const element = fieldtype === "Select" ? "select" : "input";
		let selector = `[data-fieldname="${fieldname}"]:not(.search) ${element}:visible`;

		if (fieldtype === "Text Editor") {
			selector = `[data-fieldname="${fieldname}"] .ql-editor[contenteditable=true]:visible`;
		}
		if (fieldtype === "Code") {
			selector = `[data-fieldname="${fieldname}"] .ace_text-input`;
		}
		if (fieldtype === "Markdown Editor") {
			selector = `[data-fieldname="${fieldname}"] .ace-editor-target`;
		}

		return this.page.locator(selector).first();
	}

	async fill_field(fieldname, value, fieldtype = "Data") {
		const input = this.get_field(fieldname, fieldtype);
		await this.open_picker(input, fieldtype);

		if (["Link", "Dynamic Link"].includes(fieldtype)) {
			const dropdown = input.locator("xpath=..").getByRole("listbox");
			await input.clear();
			await input.focus();
			await expect(dropdown).toBeVisible();
			await input.pressSequentially(value, { delay: 100 });
			await expect(dropdown.locator("div[role='option']").first()).toContainText(value);
			await input.press("Enter");
			await input.blur();
			await expect(dropdown).toHaveCount(0);
			await expect(input).toHaveValue(value);
		} else if (fieldtype === "Select") {
			await input.selectOption(value);
		} else {
			await this.type(input, value);
		}
		return input;
	}

	async type(input, value) {
		await input.focus();
		await input.press("End");
		await input.pressSequentially(String(value), { delay: 20 });
	}

	get_table_field(table_fieldname, row_idx, fieldname, fieldtype = "Data") {
		const row = `.frappe-control[data-fieldname="${table_fieldname}"] [data-idx="${row_idx}"]`;

		if (fieldtype === "Text Editor") {
			return this.page.locator(
				`${row} [data-fieldname="${fieldname}"] .ql-editor[contenteditable=true]`
			);
		}
		if (fieldtype === "Code") {
			return this.page.locator(`${row} [data-fieldname="${fieldname}"] .ace_text-input`);
		}
		return this.page
			.locator(`${row} [data-fieldname="${fieldname}"]`)
			.locator(".form-control:visible, .static-area:visible")
			.first();
	}

	async fill_table_field(table_fieldname, row_idx, fieldname, value, fieldtype = "Data") {
		const input = this.get_table_field(table_fieldname, row_idx, fieldname, fieldtype);
		await this.open_picker(input, fieldtype);

		if (fieldtype === "Select") {
			await input.selectOption(value);
		} else {
			await this.type(input, value);
		}
		return input;
	}

	async open_picker(input, fieldtype) {
		if (!["Date", "Time", "Datetime"].includes(fieldtype)) {
			return;
		}
		await input.click();
		// the picker rewrites the input from its own selection once its show transition ends
		await expect(this.page.locator(".datepickers-container .datepicker.active")).toHaveCSS(
			"opacity",
			"1"
		);
		if (fieldtype === "Time") {
			await input.clear();
		}
	}

	async select_form_tab(label) {
		await this.page
			.locator(".form-tabs-list [data-toggle='tab']", { hasText: label })
			.first()
			.click();
	}

	async dialog(options) {
		const dialog = await this.page.evaluateHandle((options) => {
			const dialog = new frappe.ui.Dialog(options);
			dialog.show();
			return dialog;
		}, options);
		// a dialog moves focus to its first input once it has faded in
		await this.page.waitForFunction((dialog) => dialog.display, dialog);
		return dialog;
	}

	get_open_dialog() {
		return this.page.locator(".modal:visible").last();
	}

	async hide_dialog() {
		await this.get_open_dialog().locator(".btn-modal-close").click();
		await expect(this.page.locator(".modal:visible")).toHaveCount(0);
	}

	async save() {
		const saved = this.page.waitForResponse((res) =>
			res.url().includes("/api/method/frappe.desk.form.save.savedocs")
		);
		// a field that commits its value on blur re-renders the toolbar and swallows the click
		await this.page.evaluate(() => document.activeElement?.blur());
		await this.page.locator('.page-container:visible button[data-label="Save"]').click();
		return await saved;
	}

	async open_list_filter() {
		await this.page.locator(".filter-section .filter-button").click();
		await expect(this.page.locator(".filter-popover")).toBeAttached();
	}

	// a second click on the Filter button closes the panel
	async close_list_filter() {
		await this.page.locator(".filter-section .filter-button").click();
		await expect(this.page.locator(".filter-popover")).toHaveCount(0);
	}

	// a filter row's field picker opens as a combobox panel in <body>
	async pick_filter_field(label) {
		const input = this.page.locator(
			".es-combobox__panel[data-state='open'] .es-combobox__input"
		);
		await input.fill(label);
		await input.press("Enter");
	}

	async clear_filters() {
		// saved filters are applied before the first refresh, so let that one render first
		await expect(
			this.page.locator(".list-paging-area:visible, .no-result:visible").first()
		).toBeVisible();
		if (!(await this.page.evaluate(() => cur_list.filter_area.get().length))) {
			return;
		}
		const filtered_data = await this.page.evaluateHandle(() => cur_list.data);
		await this.page.locator(".filter-x-button").dispatchEvent("click");
		await this.page.waitForFunction((data) => cur_list.data !== data, filtered_data);
	}

	async click_custom_action_button(name) {
		await this.page
			.locator(`.custom-actions [data-label="${encodeURIComponent(name)}"]`)
			.click();
	}

	async click_action_button(name) {
		await this.page.getByRole("button", { name: "Actions", exact: true }).click();
		await this.click_menu_item(name);
	}

	async click_menu_button(name) {
		await this.page.locator(".standard-actions .menu-btn-group > button").click();
		await this.click_menu_item(name);
	}

	async click_menu_item(name) {
		await this.page.locator('.es-menu [role="menuitem"]', { hasText: name }).first().click();
	}

	async click_modal_primary_button(name) {
		await this.page
			.locator(".modal-footer > .standard-actions > .btn-modal-primary:visible", {
				hasText: name,
			})
			.first()
			.click();
	}

	get listview_row_items() {
		return this.page.locator(
			".list-row > .level-left > .list-subject > .level-item > .ellipsis"
		);
	}

	async click_listview_row_item(row_no) {
		await this.listview_row_items.nth(row_no).click();
	}

	async click_listview_row_item_with_text(text) {
		await this.listview_row_items.filter({ hasText: text }).first().click();
	}

	async click_primary_button(name) {
		await this.page.locator(".primary-action:visible", { hasText: name }).first().click();
	}

	async click_form_section(name) {
		await this.page.locator(".section-head", { hasText: name }).first().click();
	}
}
