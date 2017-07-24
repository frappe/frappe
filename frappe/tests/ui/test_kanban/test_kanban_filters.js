QUnit.module('views');

QUnit.test("Test filters [Kanban view]", function(assert) {
	assert.expect(2);
	let done = assert.async();

	frappe.run_serially([
		() => frappe.tests.setup_doctype('User'),
		() => frappe.tests.setup_doctype('Kanban Board'),
		() => frappe.tests.create_todo(5),
		() => frappe.set_route("List", "ToDo", "Kanban", "kanban 1"),
		() => frappe.timeout(1),
		() => {
			assert.deepEqual(frappe.get_route(), ["List", "ToDo", "Kanban", "kanban 1"], "Kanban view opened successfully.");
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
			assert.equal(i, count, "All elements present contains data as per filters.");
		},
		() => done()
	]);
});