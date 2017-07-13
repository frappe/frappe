QUnit.module('views');

QUnit.only("Test quick entry", function(assert) {
	assert.expect(0);
	let done = assert.async();
	let random_text = frappe.utils.get_random(10);

	frappe.run_serially([
		() => frappe.set_route('List', 'ToDo'),
		() => frappe.new_doc('ToDo'),
		() => frappe.quick_entry.dialog.set_value('description', random_text),
		() => frappe.quick_entry.insert(),
		(doc) => {
			assert.ok(doc && !doc.__islocal, "Document exists");
			return frappe.set_route('Form', 'ToDo', doc.name);
		},
		() => assert.ok(cur_frm.doc.description.includes(random_text), "ToDo created"),

		// Delete the created ToDo
		() => frappe.tests.click_page_head_item('Menu'),
		() => frappe.tests.click_dropdown_item('Delete'),
		() => frappe.tests.click_page_head_item('Yes'),
		() => frappe.timeout(2),

		() => done()
	]);
});

QUnit.test("Test list values", function(assert) {
	assert.expect(2);
	let done = assert.async();

	frappe.run_serially([
		() => frappe.set_route('List', 'DocType'),
		() => frappe.timeout(2),
		() => {
			assert.deepEqual(['List', 'DocType', 'List'], frappe.get_route());
			assert.ok($('.list-item:visible').length > 10);
		},
		() => done()
	]);
});
