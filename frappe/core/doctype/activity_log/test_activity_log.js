/* eslint-disable */
// rename this file from _test_[name] to test_[name] to activate
// and remove above this line

QUnit.test("test: Activity Log", function (assert) {
	let done = assert.async();

	// number of asserts
	assert.expect(1);

	frappe.run_serially([
		// Update a DocType to update feed
		() => frappe.set_route('Form', 'DocType', 'Supplier'),
		() => cur_frm.save(),

		() => frappe.timeout(2),
		() => frappe.set_route('List','Activity Log'),

		() => frappe.timeout(1),
		() => {
			assert.ok(cur_list.data[0].subject == 'Supplier');
		},
		() => done()
	]);

});
