QUnit.test("test quick entry", function(assert) {
	assert.expect(2);
	let done = assert.async();
	let random = frappe.utils.get_random(10);

	frappe.set_route('List', 'ToDo')
		.then(() => {
			return frappe.new_doc('ToDo');
		})
		.then(() => {
			frappe.quick_entry.dialog.set_value('description', random);
			return frappe.quick_entry.insert();
		})
		.then((doc) => {
			assert.ok(doc && !doc.__islocal);
			return frappe.set_route('Form', 'ToDo', doc.name);
		})
		.then(() => {
			assert.ok(cur_frm.doc.description.includes(random));
			done();
		});
});

QUnit.test("test list values", function(assert) {
	assert.expect(2);
	let done = assert.async();
	frappe.set_route('List', 'DocType')
		.then(() => {
			assert.deepEqual(['List', 'DocType', 'List'], frappe.get_route());
			assert.ok($('.list-item:visible').length > 10);
			done();
		});
});