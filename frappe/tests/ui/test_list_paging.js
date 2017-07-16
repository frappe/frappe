QUnit.module('views');

QUnit.test("Test paging in list", function(assert) {
	assert.expect(3);
	let done = assert.async();

	frappe.run_serially([
		() => frappe.set_route('List', 'DocType'),
		() => frappe.timeout(0.5),
		() => assert.deepEqual(['List', 'DocType', 'List'], frappe.get_route(), "List opened successfully."),
		//check elements less then page length [20 in this case]
		() => assert.ok(cur_list.data.length <= cur_list.page_length, "20 or less elements are visible."),
		() => frappe.tests.click_and_wait('.btn-sm:contains("100"):visible'),
		//check elements less then page length [100 in this case]
		() => assert.ok(cur_list.data.length <= cur_list.page_length, "100 or less elements are visible."),
		() => done()
	]);
});