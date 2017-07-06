QUnit.module('views');

QUnit.test("Gantt View Tests", function(assert) {
	assert.expect(2);
	let done = assert.async();
	let randomText = frappe.utils.get_random(10);
	let inception_datetime = frappe.datetime.get_today()+" 16:20:35"; //arbitrary value taken to prevent cases like 12a for 12:00am and 12h to 24h conversion;
	let cessation_datetime = frappe.datetime.get_today()+" 18:30:45"; //arbitrary value taken to prevent cases like 12a for 12:00am and 12h to 24h conversion;();

	let event_id = () => {
		let event_label = $('.bar-label').text()
		let init = event_label.indexOf('(');
		let fin = event_label.indexOf(')');
		return (event_label.substr(init+1,fin-init-1));
	};


	frappe.run_serially([
		// Make an event
		() => {
			return frappe.tests.make("Event", [
				{subject: randomText},
				{starts_on: inception_datetime},
				{ends_on: cessation_datetime},
				{event_type: 'Private'}
			]);
		},

		// Check if event is created
		() => frappe.set_route(["List", "Event", "Gantt"]),
		() => assert.ok($('#bar > g > g.bar-group > text:visible').text().includes(randomText)),

		// Delete event 
		() => frappe.set_route(["List", "Event", "Gantt"]),
		() => frappe.timeout(0.3),
		() => frappe.set_route(["Form", "Event", event_id()]),

		() => frappe.tests.click_page_head_item('Menu'),
		() => frappe.tests.click_menu_item('Delete'),
		() => frappe.tests.click_page_head_item('Yes'),
		() => frappe.timeout(0.3),
		() => frappe.set_route(["List", "Event", "Gantt"]),
		() => frappe.timeout(0.3),

		// Check if event is deleted
		() => assert.ok($('#bar > g > g.bar-group > text:visible').text().includes("")),

		() => done()
	]);
});