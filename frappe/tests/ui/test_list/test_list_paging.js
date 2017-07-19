QUnit.module('views');

QUnit.test("Test paging in list view", function(assert) {
	assert.expect(5);
	let done = assert.async();

	frappe.run_serially([
		() => frappe.set_route('List', 'DocType'),
		() => frappe.timeout(0.5),
		() => assert.deepEqual(['List', 'DocType', 'List'], frappe.get_route(),
			"List opened successfully."),
		//check elements less then page length [20 in this case]
		() => assert.equal(cur_list.data.length, 20, 'show 20 items'),
		() => frappe.click_button('More'),
		() => frappe.timeout(2),
		() => assert.equal(cur_list.data.length, 40, 'show more items'),
		() => frappe.click_button('100', '.btn-group-paging'),
		() => frappe.timeout(2),
		() => assert.ok(cur_list.data.length > 40, 'show 100 items'),
		() => frappe.click_button('20', '.btn-group-paging'),
		() => frappe.timeout(2),
		() => assert.equal(cur_list.data.length, 20, 'show 20 items again'),
		() => done()
	]);
});