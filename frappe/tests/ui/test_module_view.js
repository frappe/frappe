QUnit.module('views');

QUnit.test("Test modules view", function(assert) {
	assert.expect(4);
	let done = assert.async();

	frappe.run_serially([

		//click Document Share Report in Permissions section [Report]
		() => frappe.set_route("modules", "Setup"),
		() => frappe.timeout(0.5),
		() => frappe.click_link('Document Share Report'),
		() => assert.deepEqual(frappe.get_route(), ["Report", "DocShare", "Document Share Report"],
			'document share report'),

		//click Print Setting in Printing section [Form]
		() => frappe.set_route("modules", "Setup"),
		() => frappe.timeout(0.5),
		() => frappe.click_link('Print Settings'),
		() => assert.deepEqual(frappe.get_route(), ["Form", "Print Settings"],
			'print settings'),

		//click Workflow Action in Workflow section [List]
		() => frappe.set_route("modules", "Setup"),
		() => frappe.timeout(0.5),
		() => frappe.click_link('Workflow Action'),
		() => assert.deepEqual(frappe.get_route(), ["List", "Workflow Action", "List"],
			'workflow action'),

		//click Workflow Action in Workflow section [List]
		() => frappe.set_route("modules"),
		() => frappe.timeout(0.5),
		() => frappe.click_link('Tools'),
		() => frappe.timeout(0.5),
		() => frappe.click_link('To Do'),
		() => assert.deepEqual(frappe.get_route(), ["List", "ToDo", "List"],
			'todo list'),

		() => done()
	]);
});
