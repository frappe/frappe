QUnit.module('views');

QUnit.test("Calendar View Tests", function(assert) {
	assert.expect(3);
	let done = assert.async();
	let random_text = frappe.utils.get_random(3);
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
		// create 2 events, one private, one public
		() => frappe.tests.make("Event", [
			{subject: random_text + ':Pri'},
			{starts_on: today},
			{event_type: 'Private'}
		]),

		() => frappe.tests.make("Event", [
			{subject: random_text + ':Pub'},
			{starts_on: today},
			{event_type: 'Public'}
		]),

		// Goto Calendar view
		() => frappe.set_route(["List", "Event", "Calendar"]),
		() => {
			// clear filter
			$('[data-fieldname="event_type"]').val('').trigger('change');
		},
		() => frappe.timeout(2),
		// Check if event is created
		() => {
			// Check if the event exists and if its title matches with the one created
			assert.ok(event_title_text().includes(random_text + ':Pri'),
				"Event title verified");
			// Check if time of event created is correct

			// assert.ok(visible_time().includes("4:20"),
			// 	"Event start time verified");
		},

		// check filter
		() => {
			$('[data-fieldname="event_type"]').val('Public').trigger('change');
		},
		() => frappe.timeout(1),
		() => {
			// private event should be hidden
			assert.notOk(event_title_text().includes(random_text + ':Pri'),
				"Event title verified");
		},

		// Delete event
		// Goto Calendar view
		() => frappe.set_route(["List", "Event", "Calendar"]),
		() => frappe.timeout(1),
		// delete event
		() => frappe.click_link(random_text + ':Pub'),
		() => {
			frappe.tests.click_page_head_item('Menu');
			frappe.tests.click_dropdown_item('Delete');
		},
		() => frappe.timeout(0.5),
		() => frappe.click_button('Yes'),
		() => frappe.timeout(2),
		() => frappe.set_route(["List", "Event", "Calendar"]),
		() => frappe.click_button("Refresh"),
		() => frappe.timeout(1),

		// Check if event is deleted
		() => assert.notOk(event_title_text().includes(random_text + ':Pub'),
			"Event deleted"),
		() => done()
	]);
});