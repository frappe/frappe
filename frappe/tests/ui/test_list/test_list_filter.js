QUnit.module('views');

QUnit.test("Test list filters", function(assert) {
	assert.expect(3);
	let done = assert.async();

	frappe.run_serially([
		() => {
			return frappe.tests.make('ToDo', [
				{description: 'low priority'},
				{priority: 'Low'}
			]);
		},
		() => {
			return frappe.tests.make('ToDo', [
				{description: 'high priority'},
				{priority: 'High'}
			]);
		},
		() => frappe.set_route('List', 'ToDo', 'List'),
		() => frappe.timeout(0.5),
		() => {
			assert.deepEqual(['List', 'ToDo', 'List'], frappe.get_route(),
				"List opened successfully.");
			//set filter values
			return frappe.set_control('priority', 'Low');
		},
		() => frappe.timeout(0.5),
		() => cur_list.page.btn_secondary.click(),
		() => frappe.timeout(1),
		() => {
			assert.equal(cur_list.data[0].priority, 'Low',
				'visible element has low priority');
			let non_low_items = cur_list.data.filter(d => d.priority != 'Low');
			assert.equal(non_low_items.length, 0, 'no item without low priority');
		},
		() => done()
	]);
});