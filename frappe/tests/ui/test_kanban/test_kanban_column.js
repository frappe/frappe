QUnit.module('views');

QUnit.test("Test: Setting column colour [Kanban view]", function(assert) {
	assert.expect(3);
	let done = assert.async();
	function get_column(name, colour) {
		return ('.kanban-column:contains('+name+')>div>div>ul>li>div.'+colour);
	}

	frappe.run_serially([
		() => frappe.set_route("List", "ToDo", "Kanban", "Kanban test"),
		() => frappe.timeout(1),
		() => assert.deepEqual(["List", "ToDo", "Kanban", "Kanban test"], frappe.get_route(),
			"Kanban view opened successfully."),
		() => {
			// set colour for columns
			$(get_column('High', "red")).click();
			$(get_column('Medium', "green")).click();
			$(get_column('Low', "yellow")).click();
		},
		() => frappe.timeout(1),
		() => {
			//check if different colours are set
			assert.equal($('.red > span')[0].innerText, 'High',
				"Colour is set for kanban column.");
			assert.equal($('.green > span')[0].innerText, 'Medium',
				"Different colour is set for other column.");
		},
		() => done()
	]);
});