QUnit.module('views');

QUnit.test("Test: Filters [Kanban view]", function(assert) {
	assert.expect(3);
	let done = assert.async();

	frappe.run_serially([
		() => frappe.set_route("List", "ToDo", "Kanban", "Kanban test"),
		() => frappe.timeout(1),
		() => {
			assert.deepEqual(["List", "ToDo", "Kanban", "Kanban test"], frappe.get_route(),
				"Kanban view opened successfully.");
		},
		// set filter values
		() => cur_list.filter_area.add('ToDo', 'priority', '=', 'Low'),
		() => frappe.timeout(1),
		() => cur_list.page.btn_secondary.click(),
		() => frappe.timeout(1),
		() => {
			assert.equal(cur_list.data[0].priority, 'Low',
				'visible element has low priority');
			let non_low_items = cur_list.data.filter(d => d.priority != 'Low');
			assert.equal(non_low_items.length, 0, 'No item without low priority');
		},
		() => done()
	]);
});