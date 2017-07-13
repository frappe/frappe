QUnit.module('views');

QUnit.test("Calendar View Tests", function(assert) {
	assert.expect(7);
	let done = assert.async();
	let random_text = frappe.utils.get_random(10);
	let today = frappe.datetime.get_today()+" 16:20:35"; //arbitrary value taken to prevent cases like 12a for 12:00am and 12h to 24h conversion
	let visible_time = () => {
		// Method to return the start-time (hours) of the event visible  
		return $('.fc-time').text().split('p')[0]; // 'p' because the arbitrary time is pm 
	};
	let event_title_text = () => {
		// Method to return the title of the event visible  
		return $('.fc-title:visible').text();
	};

	frappe.run_serially([
		// Create an event using the frappe API
		() => frappe.tests.make("Event", [
			{subject: random_text},
			{starts_on: today},
			{event_type: 'Private'}
		]),

		// Goto Calendar view
		() => frappe.set_route(["List", "Event", "Calendar"]),
		() => frappe.tests.click_page_head_item("Refresh"),
		() => frappe.timeout(0.3),
		// Check if event is created
		() => {
			// Check if the event exists and if its title matches with the one created
			assert.ok(event_title_text().includes(random_text), "Event title verified");
			// Check if time of event created is correct
			assert.ok(visible_time().includes("4:20"), "Event start time verified");
		},

		// Delete event 
		// Goto Calendar view
		() => frappe.set_route(["List", "Event", "Calendar"]),
		() => frappe.timeout(0.3),
		// Open the event to be deleted
		() => frappe.tests.click_generic_text(random_text),
		() => frappe.tests.click_page_head_item('Menu'),
		() => frappe.tests.click_dropdown_item('Delete'),
		() => frappe.tests.click_page_head_item('Yes'),
		() => frappe.timeout(4),
		// Goto Calendar View
		() => frappe.set_route(["List", "Event", "Calendar"]),
		() => frappe.timeout(0.3),

		// Check if all menu items redirect to correct locations
		// Check if clicking on 'Import' redirects you to ["data-import-tool"]
		() => frappe.tests.click_page_head_item('Menu'),
		() => frappe.tests.click_dropdown_item('Import'),
		() => assert.deepEqual(["data-import-tool"], frappe.get_route(), "Routed to 'data-import-tool' by clicking on 'Import'"),
		() => window.history.back(),
		() => frappe.timeout(0.5),
			
		// Check if clicking on 'User Permissions Manager' redirects you to ["user-permissions"]
		() => frappe.tests.click_page_head_item('Menu'),
		() => frappe.tests.click_dropdown_item('User Permissions Manager'),
		() => assert.deepEqual(["user-permissions"], frappe.get_route(), "Routed to 'user-permissions' by clicking on 'User Permissions Manager'"),
		() => window.history.back(),
		() => frappe.timeout(0.5),
			
		// Check if clicking on 'Role Permissions Manager' redirects you to ["permission-manager"]
		() => frappe.tests.click_page_head_item('Menu'),
		() => frappe.tests.click_dropdown_item('Role Permissions Manager'),
		() => assert.deepEqual(["permission-manager"], frappe.get_route(), "Routed to 'permission-manager' by clicking on 'Role Permissions Manager'"),
		() => window.history.back(),
		() => frappe.timeout(0.5),
			
		// Check if clicking on 'Customize' redirects you to ["Form", "Customize Form"]
		() => frappe.tests.click_page_head_item('Menu'),
		() => frappe.tests.click_dropdown_item('Customize'),
		() => assert.deepEqual(["Form", "Customize Form"], frappe.get_route(), "Routed to 'Form, Customize Form' by clicking on 'Customize'"),
		() => window.history.back(),
		() => frappe.timeout(0.5),

		// Check if event is deleted
		() => assert.equal(event_title_text(), "", "Event deleted"),	

		() => done()

	]);
});