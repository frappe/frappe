QUnit.module('form');

QUnit.test("Test Linked With", function(assert) {
	assert.expect(2);
	const done = assert.async();

	frappe.run_serially([
		() => frappe.set_route('Form', 'Module Def', 'Contacts'),
		() => frappe.tests.click_page_head_item('Menu'),
		() => frappe.tests.click_dropdown_item('Links'),
		() => frappe.timeout(4),
		() => {
			assert.equal(cur_dialog.title, 'Linked With', 'Linked with dialog is opened');
			const link_tables_count = cur_dialog.$wrapper.find('.list-item-table').length;
			assert.equal(link_tables_count, 2, 'Two DocTypes are linked with Contacts');
		},
		done
	]);
});