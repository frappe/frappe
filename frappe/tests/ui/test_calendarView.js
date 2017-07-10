QUnit.module('views');

QUnit.test("Calendar View Tests", function(assert) {
	assert.expect(8);
	let done = assert.async();
	let randomText = frappe.utils.get_random(10);
	let today = frappe.datetime.get_today()+" 16:20:35"; //arbitrary value taken to prevent cases like 12a for 12:00am and 12h to 24h conversion
	let visibleHours = () => {return $('.fc-time').text().split(':')[0].replace(/\D+/g, '')};
	let visibleMinutes = () => {return $('.fc-time').text().split(':')[1].replace(/\D+/g, '')};

	frappe.run_serially([
		// Make an event
		() => frappe.tests.make("Event", [
			{subject: randomText},
			{starts_on: today},
			{event_type: 'Private'}
		]),

		() => frappe.set_route(["List", "Event", "Calendar"]),


		// Check if event is created
		() => {
			assert.equal($('.fc-title').text(), randomText);
			// Check if time of event created is correct
			assert.equal(visibleHours(), 4);
			assert.equal(visibleMinutes(), 20);
		},

		// Delete event 
		() => frappe.set_route(["List", "Event", "Calendar"]),
		() => frappe.timeout(0.3),
		() => frappe.tests.click_generic_text(randomText),
		() => frappe.tests.click_page_head_item('Menu'),
		() => frappe.tests.click_menu_item('Delete'),
		() => frappe.tests.click_page_head_item('Yes'),
		() => frappe.timeout(4),
		() => frappe.set_route(["List", "Event", "Calendar"]),
		() => frappe.timeout(0.3),

		// Check if all menu items redirect to correct locations
		() => frappe.tests.click_page_head_item('Menu'),
		() => frappe.tests.click_menu_item('Import'),
		() => assert.deepEqual(["data-import-tool"], frappe.get_route()),
		() => window.history.back(),
		() => frappe.timeout(0.5),

		() => frappe.tests.click_page_head_item('Menu'),
		() => frappe.tests.click_menu_item('User Permissions Manager'),
		() => assert.deepEqual(["user-permissions"], frappe.get_route()),
		() => window.history.back(),
		() => frappe.timeout(0.5),

		() => frappe.tests.click_page_head_item('Menu'),
		() => frappe.tests.click_menu_item('Role Permissions Manager'),
		() => assert.deepEqual(["permission-manager"], frappe.get_route()),
		() => window.history.back(),
		() => frappe.timeout(0.5),

		() => frappe.tests.click_page_head_item('Menu'),
		() => frappe.tests.click_menu_item('Customize'),
		() => assert.deepEqual(["Form", "Customize Form"], frappe.get_route()),
		() => window.history.back(),
		() => frappe.timeout(0.5),

		// Check if event is deleted
		() => assert.deepEqual($('.fc-title').text(), ""),	

		() => done()

	]);
});