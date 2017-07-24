QUnit.module('views');

QUnit.test("Test: Kanban view", function(assert) {
	assert.expect(3);
	let done = assert.async();
	let total_elements;

	frappe.run_serially([
		() => frappe.set_route("List", "ToDo", "List"),
		// calculate number of element in list
		() => frappe.timeout(1),
		() => total_elements = cur_list.data.length,
		() => frappe.set_route("List", "ToDo", "Kanban", "Kanban test"),
		() => frappe.timeout(1),
		() => {
			assert.equal('Kanban', cur_list.current_view,
				"Current view is kanban.");
			assert.equal("Kanban test", cur_list.list_renderer.page_title,
				"Kanban view opened successfully.");
			// check if all elements are visible in kanban view
			assert.equal(total_elements, cur_list.data.length,
				"All elements are visible in kanban view.");
		},
		() => done()
	]);
});