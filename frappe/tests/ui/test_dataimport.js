//Test to export a file

QUnit.test("test data-export-tool", function(assert) {
	assert.expect(1);
	var f=0;
	let done = assert.async();
	frappe.run_serially([
		() => frappe.set_route('data-import-tool'),
		() => $('select.doctype').val("Task").change(),
		() => frappe.timeout(2),
		() => $('.btn-select-mandatory').click(),
		() => frappe.timeout(2),
		//To count the number of mandatory fields of a doctype
		() => { for (var i = 0; i < frappe.get_meta("Task").fields.length; i++) 
		{	
			if(frappe.get_meta("Task").fields[i].reqd == 1)
				f++;
		}
	},
		() => $('.btn-download-data').click(),
		() => frappe.timeout(3),
		//To determine if the number of fields checked are mandatory
		() => { assert.ok($('input.select-column-check:checked').length == f); },
		() => done()
	]);
});
