/* eslint-disable */
// rename this file from _test_[name] to test_[name] to activate
// and remove above this line

QUnit.test("test: Calendar View", function (assert) {
	let done = assert.async();

	// number of asserts
	assert.expect(4);

	const calendar_view = 'Test Calendar View ' + frappe.utils.get_random(5)

	frappe.run_serially([
		// insert a new Calendar View
		() => frappe.tests.make('Calendar View', [
			// values to be set
			{__newname: calendar_view},
			{reference_doctype: 'Event'},
			{subject_field: 'subject'},
			{start_date_field: 'starts_on'},
			{end_date_field: 'ends_on'}
		]),
		() => {
			assert.equal(cur_frm.doc.name, calendar_view);
			assert.equal(cur_frm.doc.subject_field, 'subject');
		},
		() => frappe.tests.click_button('Show Calendar'),
		() => frappe.timeout(2),
		() => {
			console.log(frappe.get_route_str())
			assert.equal(frappe.get_route_str(), `List/Event/Calendar/${calendar_view}`, 'Route set correctly')
			assert.ok($(`.page-title:visible:contains("${calendar_view}")`).length, 'Page title set correctly');
		},
		() => done()
	]);

});
