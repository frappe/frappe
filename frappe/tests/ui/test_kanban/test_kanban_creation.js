QUnit.module('views');

QUnit.test("Test: Creation [Kanban view]", function(assert) {
	assert.expect(2);
	let done = assert.async();

	frappe.run_serially([
		() => frappe.set_route("List", "ToDo", "List"),
		// click kanban in side bar
		() => frappe.click_link('Kanban'),
		() => frappe.click_link('New Kanban Board'),
		() => frappe.timeout(0.5),
		// create new kanban
		() => {
			assert.equal(cur_dialog.title, 'New Kanban Board',
				"Dialog for new kanban opened.");
			cur_dialog.set_value('board_name', 'Kanban test');
			cur_dialog.set_value('field_name', 'Priority');
		},
		() => frappe.timeout(0.5),
		() => cur_dialog.get_primary_btn().click(),
		() => frappe.timeout(1),
		() => frappe.set_route("List", "Kanban Board", "List"),
		() => frappe.timeout(0.5),
		// check in kanban list if new kanban is created
		() => assert.equal(cur_list.data[0].name, 'Kanban test',
			"Added kanban is visible in kanban list."),
		() => done()
	]);
});