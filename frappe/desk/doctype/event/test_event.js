
QUnit.test("test: Event", function (assert) {
	let done = assert.async();

	// number of asserts
	assert.expect(4);

	const subject = '_Test Event 1';
	const datetime = frappe.datetime.now_datetime();
	const hex = '#6be273';
	const rgb = 'rgb(107, 226, 115)';

	frappe.run_serially([
		// insert a new Event
		() => frappe.tests.make('Event', [
			// values to be set
			{subject: subject},
			{starts_on: datetime},
			{color: hex},
			{event_type: 'Private'}
		]),
		() => {
			assert.equal(cur_frm.doc.subject, subject, 'Subject correctly set');
			assert.equal(cur_frm.doc.starts_on, datetime, 'Date correctly set');
			assert.equal(cur_frm.doc.color, hex, 'Color correctly set');

			// set filters explicitly for list view
			frappe.route_options = {
				event_type: 'Private'
			};
		},
		() => frappe.set_route('List', 'Event', 'Calendar'),
		() => frappe.timeout(2),
		() => {
			const bg_color = $(`.result:visible .fc-day-grid-event:contains("${subject}")`)
				.css('background-color');
			assert.equal(bg_color, rgb, 'Event background color is set correctly');
		},
		() => done()
	]);

});
