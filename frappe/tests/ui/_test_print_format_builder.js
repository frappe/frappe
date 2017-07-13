QUnit.module('views');

QUnit.only("Print Format Builder", function(assert) {
	assert.expect(0);
	let random_text = frappe.utils.get_random(10);
	let done = assert.async();
	let click_custoize = () => {
		return $(`.btn-print-edit`).click();
	};

	frappe.run_serially([
		() => frappe.set_route(["List", "ToDo", "List"]),
		() => frappe.timeout(0.3),

		() => frappe.new_doc('ToDo'),
		() => frappe.quick_entry.dialog.set_value('description', random_text),
		() => frappe.quick_entry.insert(),
		() => frappe.timeout(0.5),

		() => frappe.tests.click_page_head_item('Refresh'),
		() => frappe.timeout(0.3),
		
		() => frappe.tests.click_generic_text(random_text),
		() => frappe.tests.click_print_logo(),

		() => click_custoize(),
		() => frappe.timeout(1),
		() => $(`div.control-input > input:visible`).val('custom_todo'),
		() => frappe.timeout(0.3),

		() => frappe.tests.click_generic_text('Start', 'button'),
		() => frappe.timeout(1),

		() => frappe.tests.click_page_head_item('Save'),

		() => frappe.tests.click_generic_text('Edit Properties', 'button'),
		() => frappe.tests.click_page_head_item('Menu'),
		() => frappe.tests.click_dropdown_item('Delete'),
		() => frappe.tests.click_page_head_item('Yes'),
		() => frappe.timeout(1),

		() => frappe.set_route(["List", "ToDo", "List"]),
		() => frappe.timeout(0.3),
		() => frappe.tests.click_generic_text(random_text),
		() => frappe.tests.click_page_head_item('Menu'),
		() => frappe.tests.click_dropdown_item('Delete'),
		() => frappe.tests.click_page_head_item('Yes'),

		() => frappe.timeout(2),

		() => done()
	]);
});


// when you do a pull, hopefully after a merge ... make sure edit the options method in global_search