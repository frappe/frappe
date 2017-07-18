QUnit.module('views');

QUnit.test("Test deletion of one list element [List view]", function(assert) {
	assert.expect(3);
	let done = assert.async();
	let count;
	let random;

	frappe.run_serially([
		() => frappe.tests.setup_doctype('User'),
		() => frappe.tests.create_todo(2),
		() => frappe.set_route('List', 'ToDo', 'List'),
		() => frappe.timeout(0.5),
		() => {
			assert.deepEqual(['List', 'ToDo', 'List'], frappe.get_route(), "List opened successfully.");
			//total list elements
			count = cur_list.data.length;
			random = Math.floor(Math.random() * (count) + 1);
			//select one element randomly
			$('div:nth-child('+random+')>div>div>.list-row-checkbox').click();
		},
		() => cur_list.page.btn_primary.click(),
		() => frappe.timeout(0.5),
		() => {
			//check if asking for confirmation and click yes
			assert.equal("Confirm", cur_dialog.title, "Asking for confirmation.");
			cur_dialog.primary_action(frappe.confirm);
		},
		() => frappe.timeout(1),
		//check if total elements decreased by one
		() => assert.equal(cur_list.data.length, (count-1), "Only one element is deleted."),
		() => done()
	]);
});

QUnit.test("Test deletion of all list element [List view]", function(assert) {
	assert.expect(3);
	let done = assert.async();

	frappe.run_serially([
		() => frappe.tests.setup_doctype('User'),
		() => frappe.tests.create_todo(5),
		() => frappe.set_route('List', 'ToDo', 'List'),
		() => frappe.timeout(0.5),
		() => {
			assert.deepEqual(['List', 'ToDo', 'List'], frappe.get_route(), "List opened successfully.");
			//select all element
			$('.list-select-all.hidden-xs').click();
		},
		() => cur_list.page.btn_primary.click(),
		() => frappe.timeout(0.5),
		() => {
			assert.equal("Confirm", cur_dialog.title, "Asking for confirmation.");
			//click yes for deletion
			cur_dialog.primary_action(frappe.confirm);
		},
		() => frappe.timeout(2),
		//check zero elements left
		() => assert.equal( cur_list.data.length, '0', "No element is present in list."),
		() => done()
	]);
});