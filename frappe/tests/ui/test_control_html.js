QUnit.module('controls');

QUnit.test("Test ControlHTML", function(assert) {
	assert.expect(3);
	const random_name = frappe.utils.get_random(3).toLowerCase();

	let done = assert.async();

	frappe.run_serially([
		() => {
			return frappe.tests.make('Custom Field', [
				{dt: 'ToDo'},
				{fieldtype: 'HTML'},
				{label: random_name},
				{options: '<h3> Test </h3>'}
			]);
		},
		() => {
			return frappe.tests.make('Custom Field', [
				{dt: 'ToDo'},
				{fieldtype: 'HTML'},
				{label: random_name + "_template"},
				{options: '<h3> Test {%= doc.status %} </h3>'}
			]);
		},
		() => frappe.set_route('List', 'ToDo'),
		() => frappe.new_doc('ToDo'),
		() => {
			if (frappe.quick_entry)
			{
				frappe.quick_entry.dialog.$wrapper.find('.edit-full').click();
				return frappe.timeout(1);
			}
		},
		() => {
			const control = $(`.frappe-control[data-fieldname="${random_name}"]`)[0];
			return assert.ok(control.innerHTML === '<h3> Test </h3>');
		},
		() => {
			const control = $(`.frappe-control[data-fieldname="${random_name}_template"]`)[0];
			return assert.ok(control.innerHTML === '<h3> Test Open </h3>');
		},
		() => frappe.tests.set_control("status", "Closed"),
		() => frappe.timeout(1),
		() => {
			const control = $(`.frappe-control[data-fieldname="${random_name}_template"]`)[0];
			return assert.ok(control.innerHTML === '<h3> Test Closed </h3>');
		},
		() => done()
	]);
});
