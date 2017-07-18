QUnit.module('views');

QUnit.test("Test list values", function(assert) {
	assert.expect(2);
	let done = assert.async();

	frappe.run_serially([
		() => frappe.set_route('List', 'DocType'),
		() => frappe.timeout(2),
		() => {
			assert.deepEqual(['List', 'DocType', 'List'], frappe.get_route(), "Routed to DocType List");
			assert.ok($('.list-item:visible').length > 10, "More than 10 items visible in DocType List");
		},
		() => done()
	]);
});