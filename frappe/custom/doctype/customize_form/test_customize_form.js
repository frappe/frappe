// try and delete a standard row, it should fail

QUnit.module('Customize Form');

QUnit.test("test customize form", function(assert) {
	assert.expect(2);
	let done = assert.async();
	frappe.run_serially([
		() => frappe.set_route('Form', 'Customize Form'),
		() => frappe.timeout(5),
		() => cur_frm.set_value('doc_type', 'ToDo'),
		() => frappe.timeout(2),

		() => assert.equal(cur_frm.doc.fields[1].fieldname, 'status',
			'check if second field is "status"'),

		// open "status" row
		() => cur_frm.fields_dict.fields.grid.grid_rows[1].toggle_view(),
		() => frappe.timeout(0.5),

		// try deleting it
		() => $('.grid-delete-row:visible').click(),

		() => frappe.timeout(0.5),
		() => frappe.hide_msgprint(),
		() => frappe.timeout(0.5),

		// status still exists
		() => assert.equal(cur_frm.doc.fields[1].fieldname, 'status',
			'check if second field is still "status"'),
		() => done()
	]);
});
