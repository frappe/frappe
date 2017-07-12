QUnit.module('views');

QUnit.test("Test creation of new kanban", function(assert) {
	assert.expect(2);
	let done = assert.async();

	frappe.run_serially([
		() => frappe.set_route("List", "ToDo", "List"),
		//click kanban in side bar
		() => frappe.tests.click_and_wait('a:contains("Kanban"):visible'),
		() => frappe.tests.click_and_wait('.new-kanban-board > a'),
		//create new kanban
		() => {
			assert.equal(cur_dialog.title, 'New Kanban Board');
			cur_dialog.set_value('board_name', 'Todo kanban');
			cur_dialog.set_value('field_name', 'Status');
			cur_dialog.get_primary_btn().click();
		},
		() => frappe.timeout(1),
		() => frappe.set_route("List", "Kanban Board", "List"),
		//check in kanban list if created
		() => assert.equal(cur_list.data[0].name, 'Todo kanban'),
		() => done()
	]);
});

QUnit.test("Test kanban view", function(assert) {
	assert.expect(2);
	let done = assert.async();
	let total_elements;

	frappe.run_serially([
		() => frappe.tests.setup_doctype('User'),
		() => frappe.tests.setup_doctype('ToDo'),
		() => frappe.tests.setup_doctype('Kanban Board'),
		() => frappe.set_route("List", "ToDo", "List"),
		//calculate number of element in list
		() => total_elements = cur_list.data.length,
		() => frappe.set_route("List", "ToDo", "Kanban", "kanban 1"),
		() => {
			//check if all elements are visible in kanban view
			assert.equal(cur_list.current_view, 'Kanban');
			assert.equal(total_elements, cur_list.data.length);
		},
		() => done()
	]);
});

QUnit.test("Test setting colour of column", function(assert) {
	assert.expect(2);
	let done = assert.async();

	frappe.run_serially([
		() => frappe.tests.setup_doctype('User'),
		() => frappe.tests.setup_doctype('ToDo'),
		() => frappe.tests.setup_doctype('Kanban Board'),
		() => frappe.set_route("List", "ToDo", "Kanban", "kanban 1"),
		() => frappe.timeout(1),
		//set colour to columns
		() => frappe.tests.click_and_wait('div:nth-child(3) > div > div > ul > li > div.red'),
		() => frappe.tests.click_and_wait('div:nth-child(4) > div > div > ul > li > div.green'),
		() => {
			//check if colours are set
			assert.equal($('.red > span')[0].innerText, 'Open');
			assert.equal($('.green > span')[0].innerText, 'Closed');
		},
		() => done()
	]);
});

QUnit.only("Test filters in kanban", function(assert) {
	assert.expect(1);
	let done = assert.async();

	frappe.run_serially([
		// () => frappe.tests.setup_doctype('User'),
		// () => frappe.tests.setup_doctype('ToDo'),
		// () => frappe.tests.setup_doctype('Kanban Board'),
		() => frappe.set_route("List", "ToDo", "Kanban", "kanban 1"),
		() => frappe.timeout(1),
		() => {
			//set filter values
			$('.col-md-2:nth-child(2) .input-sm').val('Closed');
			$('.col-md-2:nth-child(5) .input-sm').val('Administrator');
		},
		() => frappe.timeout(1),
		() => cur_list.page.btn_secondary.click(),
		() => frappe.timeout(1),
		() => {
			//get total list element
			var count = cur_list.data.length;
			//check if all elements are as per filter
			var i=0;
			for ( ; i < count ; i++)
				if ((cur_list.data[i].status!='Closed')||(cur_list.data[i].owner!='Administrator'))
					break;
			assert.equal(i, count);
		},
		() => done()
	]);
});

QUnit.skip("Test adding new column", function(assert) {
	assert.expect(0);
	let done = assert.async();

	frappe.run_serially([
		() => frappe.tests.setup_doctype('User'),
		() => frappe.tests.setup_doctype('ToDo'),
		() => frappe.tests.setup_doctype('Kanban Board'),
		() => frappe.set_route("List", "ToDo", "Kanban", "kanban 1"),
		() => frappe.timeout(1),
		() => frappe.tests.click_and_wait('a:contains("Add a column")'),
		() => {
			$('.new-column-title').val('In Progress');

		},
		() => done()
	]);
});