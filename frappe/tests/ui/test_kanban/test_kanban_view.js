QUnit.module('views');

QUnit.test("Test kanban view", function(assert) {
	assert.expect(3);
	let done = assert.async();
	let total_elements;

	frappe.run_serially([
		() => frappe.tests.setup_doctype('User'),
		() => frappe.tests.setup_doctype('Kanban Board'),
		() => frappe.tests.create_todo(3),
		() => frappe.set_route("List", "ToDo", "List"),
		//calculate number of element in list
		() => frappe.timeout(0.5),
		() => total_elements = cur_list.data.length,
		() => frappe.set_route("List", "ToDo", "Kanban", "kanban 1"),
		() => {
			assert.deepEqual(frappe.get_route(), ["List", "ToDo", "Kanban", "kanban 1"], "Kanban view opened successfully.");
			//check if all elements are visible in kanban view
			assert.equal(cur_list.current_view, 'Kanban', "Current view kanban.");
			assert.equal(total_elements, cur_list.data.length, "All elements are visible in kanban view.");
		},
		() => done()
	]);
});