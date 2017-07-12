// Test for creating query report
QUnit.test("Test Query Report", function(assert) {
	assert.expect(1);
	let done = assert.async();
	frappe.run_serially([
		() => {
			return frappe.tests.make('Report', [
				{report_name: 'ToDo List Report'},
				{report_type: 'Query Report'},
				{ref_doctype: 'ToDo'},
				{module: 'Setup'}
			]);			
		},
		() => frappe.set_route('Form','Report', 'ToDo List Report'),

		//Query
		() => cur_frm.set_value('query','Select * from `tabToDo`'),
		() => cur_frm.save(),   
			
		() => { $("form-inner-toolbar .btn-xs").click(frappe.set_route('query-report','ToDo List Report')); },	
		() => frappe.timeout(5),
		() => {
			
			assert.ok($('div.grid-canvas > div.slick-row').length>0);
			frappe.timeout(3);
		},
		() => done()
	]);
});

