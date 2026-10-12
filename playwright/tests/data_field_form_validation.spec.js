import { test, expect } from "../support";
import data_field_validation_doctype from "../fixtures/data_field_validation_doctype";

const doctype_name = data_field_validation_doctype.name;

test.describe("Data Field Input Validation in New Form", () => {
	test.beforeAll(async ({ admin }) => {
		await admin.insert_doc("DocType", data_field_validation_doctype, true);
	});

	test.beforeEach(async ({ desk }) => {
		await desk.new_form(doctype_name);
	});

	async function validate_field(desk, fieldname, invalid_value, valid_value) {
		const input = desk.get_field(fieldname);
		const control = desk.page.locator(`.frappe-control[data-fieldname="${fieldname}"]`);

		await input.clear();
		await input.pressSequentially(invalid_value);
		await input.blur();
		await expect(control).toHaveClass(/(^|\s)has-error(\s|$)/);

		await input.clear();
		await input.pressSequentially(valid_value);
		await expect(control).not.toHaveClass(/(^|\s)has-error(\s|$)/);
	}

	test.describe("Data Field Options", () => {
		test("should validate email address", async ({ desk }) => {
			await validate_field(desk, "email", "captian", "hello@test.com");
		});

		test("should validate URL", async ({ desk }) => {
			await validate_field(desk, "url", "jkl", "https://frappe.io");
			await validate_field(desk, "url", "abcd.com", "http://google.com/home");
			await validate_field(desk, "url", "&&http://google.uae", "gopher://frappe.io");
			await validate_field(
				desk,
				"url",
				"ftt2:://google.in?q=news",
				"ftps2://frappe.io/__/#home"
			);
			await validate_field(desk, "url", "ftt2://", "ntps://localhost");
		});

		test("should validate phone number", async ({ desk }) => {
			await validate_field(desk, "phone", "america", "89787878");
		});

		test("should validate name", async ({ desk }) => {
			await validate_field(desk, "person_name", " 777Hello", "James Bond");
		});
	});
});
