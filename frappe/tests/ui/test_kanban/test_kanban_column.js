QUnit.module('views');

QUnit.test("Test setting colour for column [Kanban view]", function(assert) {
	assert.expect(3);
	let done = assert.async();

	frappe.run_serially([
		() => frappe.tests.setup_doctype('Kanban Board'),
		() => frappe.set_route("List", "ToDo", "Kanban", "kanban 1"),
		() => frappe.timeout(0.5),
		() => assert.deepEqual(frappe.get_route(), ["List", "ToDo", "Kanban", "kanban 1"], "Kanban view opened successfully."),
		//set colour for columns
		() => frappe.tests.click_and_wait('div:nth-child(3) > div > div > ul > li > div.red'),
		() => frappe.tests.click_and_wait('div:nth-child(4) > div > div > ul > li > div.green'),
		() => {
			//check if different colours are set
			assert.equal($('.red > span')[0].innerText, 'Open', "Colour is set for kanban column.");
			assert.equal($('.green > span')[0].innerText, 'Closed', "Different colour is set for other column.");
		},
		() => done()
	]);
});