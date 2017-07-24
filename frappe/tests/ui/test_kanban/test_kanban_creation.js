QUnit.module('views');

QUnit.test("Test creation of new kanban [Kanban view]", function(assert) {
	assert.expect(2);
	let done = assert.async();

	frappe.run_serially([
		() => frappe.set_route("List", "ToDo", "List"),
		//click kanban in side bar
		() => frappe.tests.click_and_wait('a:contains("Kanban"):visible'),
		() => frappe.tests.click_and_wait('.new-kanban-board > a'),
		() => frappe.timeout(0.5),
		//create new kanban
		() => {
			assert.equal(cur_dialog.title, 'New Kanban Board', "Dialog for new kanban opened.");
			cur_dialog.set_value('board_name', 'Todo kanban');
			cur_dialog.set_value('field_name', 'Status');
		},
		() => frappe.timeout(0.5),
		() => cur_dialog.get_primary_btn().click(),
		() => frappe.timeout(1),
		() => frappe.set_route("List", "Kanban Board", "List"),
		() => frappe.timeout(0.5),
		//check in kanban list if new kanban is created
		() => assert.equal(cur_list.data[0].name, 'Todo kanban', "Added kanban is visible in kanban list."),
		() => done()
	]);
});