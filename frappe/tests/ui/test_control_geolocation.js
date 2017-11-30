QUnit.module('controls');

QUnit.test("Test ControlGeolocation", function(assert) {
	assert.expect(1);

	const random_name = frappe.utils.get_random(3).toLowerCase();

	let done = assert.async();

	// geolocation alert dialog suppressed (only secure origins or localhost allowed)
	window.alert = function() {
		console.log.apply(console, arguments); //eslint-disable-line
	};

	frappe.run_serially([
		() => {
			return frappe.tests.make('Custom Field', [
				{dt: 'ToDo'},
				{fieldtype: 'Geolocation'},
				{label: random_name},
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
			const control = $(`.frappe-control[data-fieldname="${random_name}"]`);

			return assert.ok(control.data('fieldtype') === 'Geolocation');
		},
		() => done()
	]);
});
