// Test for creating query report
QUnit.test("Test Query Report", function(assert){
	assert.expect(2);
	let done = assert.async();
	let random = frappe.utils.get_random(10);
	frappe.run_serially([
		() => frappe.set_route('List', 'ToDo'),
		() => frappe.new_doc('ToDo'),
		() => frappe.quick_entry.dialog.set_value('description', random),
		() => frappe.quick_entry.insert(),
		() => {
			return frappe.tests.make('Report', [
				{report_name: 'ToDo List Report'},
				{report_type: 'Query Report'},
				{ref_doctype: 'ToDo'}
			]);
		},
		() => frappe.set_route('Form','Report', 'ToDo List Report'),

		//Query
		() => cur_frm.set_value('query','select description,owner,status from `tabToDo`'),
		() => cur_frm.save(),
		() => frappe.set_route('query-report','ToDo List Report'),	
		() => frappe.timeout(5),
		() => { 
			assert.ok($('div.slick-header-column').length == 4,'Correct numbers of columns visible');
			//To check if the result is present
			assert.ok($('div.r1:contains('+random+')').is(':visible'),'Result is visible in report');
			frappe.timeout(3);
		},
		() => done()
	]);
});
