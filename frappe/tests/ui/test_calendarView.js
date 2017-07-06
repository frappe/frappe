QUnit.module('views');

QUnit.test("Create and delete an event", function(assert) {
	assert.expect(4);
	let done = assert.async();
	let randomText = frappe.utils.get_random(10);
	let today = frappe.datetime.get_datetime_as_string();

	frappe.run_serially([
		
		() => {
			return frappe.tests.make("Event", [
					{subject: randomText},
					{starts_on: today},
					{event_type: 'Private'}
			]);
		},

		() => frappe.set_route(["List", "Event", "Calendar"]),


		// Check if event is created
		() => {
			assert.deepEqual($('.fc-title').text(), randomText);
			// Check if time of event created is correct
			let reqHours = (new Date(today)).getHours();
			if ( reqHours > 12 ){
				reqHours -= 12;
			}
			else if ( (new Date(today)).getHours() == 0 ){
				reqHours = 12;
			}
			let reqMinutes = (new Date(today)).getMinutes();
			let visibleHours = $('.fc-time').text().split(':')[0].replace(/\D+/g, '');
			let visibleMinutes = $('.fc-time').text().split(':')[1].replace(/\D+/g, '');
			assert.equal(visibleHours, reqHours);
			assert.equal(visibleMinutes, reqMinutes);
		},

		// Delete event 
		() => frappe.set_route(["List", "Event", "Calendar"]),
		() => frappe.timeout(0.3),
		() => frappe.tests.clickText(randomText),
		() => frappe.tests.click_menu_button(),
		() => frappe.tests.clickText('Delete'),
		() => $('.btn-primary:visible').click(),	// hot-fix to click yes to delete
		() => frappe.timeout(0.3),
		() => frappe.set_route(["List", "Event", "Calendar"]),
		() => frappe.timeout(0.3),
		// Check if event is deleted
		() => assert.deepEqual($('.fc-title').text(), ""),	

		() => {return done();}

	]);
});