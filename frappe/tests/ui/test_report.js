// Test for creating query report

QUnit.test("test building report", function(assert) {
	assert.expect(2);
	let done = assert.async();
	frappe.run_serially([
		() => {
			return frappe.tests.make('Report', [
				{report_name: 'Selling Report'},
				{report_type: 'Query Report'},
				{ref_doctype: 'Sales Person'},
				{module: 'Setup'}
			]);			
		},
		() => {
			
			assert.ok(cur_frm.doc.report_name=='Selling Report');
			assert.ok(cur_frm.doc.report_type=='Query Report');
		},
		() => done()
	]);
});


//Test for generating report with the help of writing query

QUnit.test("test query report", function(assert) {
	assert.expect(1);
	let done = assert.async();
    frappe.run_serially([
		() => frappe.set_route('Form','Report', 'Selling Report'),

			//Query
		() => cur_frm.set_value('query','Select * from `tabSales Person`'),
		() => cur_frm.save(),   
			
		() => { $("form-inner-toolbar .btn-xs").click(frappe.set_route('query-report','Selling Report')); },	
		() => frappe.timeout(5),
			
		() => assert.deepEqual(["query-report", "Selling Report"], frappe.get_route()),
		() => done()
	]);
});

// Test for Data Export
QUnit.only("test Data Export Tool", function(assert) {
	assert.expect(1);
	let done = assert.async();
	frappe.run_serially([
	    () => frappe.set_route('data-import-tool'),
	    () => assert.deepEqual(["data-import-tool"], frappe.get_route()),
		() => { $("select.doctype").val("Activity Type").change(); },
		() => { $(".btn-download-data").click(); },
		() => frappe.timeout(5),
		() => done()
	]);
});
