QUnit.module('views');

QUnit.test("Gantt View Tests", function(assert) {
	assert.expect(2);
	let done = assert.async();
	let random_text = frappe.utils.get_random(10);
	let start_date = frappe.datetime.get_today()+" 16:20:35"; // arbitrary value taken to prevent cases like 12a for 12:00am and 12h to 24h conversion
	let end_date = frappe.datetime.get_today()+" 18:30:45"; //arbitrary value taken to prevent cases like 12a for 12:00am and 12h to 24h conversion
	let event_id = () => {
		// Method to acquire the ID of the event created. This is needed to redirect to the event page
		let event_label = $('.bar-label').text();
		let init = event_label.indexOf('(');
		let fin = event_label.indexOf(')');
		return (event_label.substr(init+1,fin-init-1));
	};
	let event_title_text = (text) => {
		// Method to check the name of the event created. This is needed to verify the creation and deletion of the event
		return $('#bar > g > g.bar-group > text:visible').text().includes(text);
	};

	frappe.run_serially([
		// Create an event using the Frapee API
		() => {
			return frappe.tests.make("Event", [
				{subject: random_text},
				{starts_on: start_date},
				{ends_on: end_date},
				{event_type: 'Private'}
			]);
		},

		// Check if event is created
		() => frappe.set_route(["List", "Event", "Gantt"]),
		() => assert.ok( event_title_text(random_text) ),

		// Delete event 
		() => frappe.set_route(["List", "Event", "Gantt"]),
		() => frappe.timeout(0.3),
		// Redirect to the event page to delete the event
		() => frappe.set_route(["Form", "Event", event_id()]),
		() => frappe.tests.click_page_head_item('Menu'),
		() => frappe.tests.click_dropdown_item('Delete'),
		() => frappe.tests.click_page_head_item('Yes'),
		() => frappe.timeout(0.3),
		() => frappe.set_route(["List", "Event", "Gantt"]),
		() => frappe.timeout(0.3),

		// Check if event is deleted
		() => assert.ok( event_title_text("") ),

		() => done()
	]);
});