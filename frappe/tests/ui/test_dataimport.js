//Test to export a file
QUnit.test("test data-export-tool", function(assert) {
	assert.expect(1);
	var f = 0;
	let done = assert.async();
	frappe.run_serially([
		() => frappe.set_route('data-import-tool'),
		() => $('select.doctype').val("Task").change(),
		() => frappe.timeout(2),
		() => $('.btn-select-mandatory').click(),
		() => frappe.timeout(2),
		//To count the number of mandatory fields of a doctype
		() => {
			var fields = frappe.get_meta("Task").fields;
			f = fields.filter(f => f.reqd).length;
		},
		() => $('.btn-download-data').click(),
		() => frappe.timeout(3),
		//To determine if the number of fields checked are mandatory
		() => {
			assert.ok($('input.select-column-check:checked').length == f);
		},
		() => done()
	]);
});