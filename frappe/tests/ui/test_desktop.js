QUnit.module('views');

QUnit.skip("Test desktop icon link verification", function(assert) {
	assert.expect(2);
	let done = assert.async();
	function icon(name) {
		return ('i[title='+name+']');
	}

	frappe.run_serially([
		() => frappe.set_route("modules_setup"),
		() => {
			$('.check-all').click();
			$('.primary-action').click();
		},
		//click file manager icon (list)
		() => frappe.set_route(),                                                ///******* need reload here ********///
		() => frappe.tests.click_and_wait(icon('"File Manager"')),
		() => assert.deepEqual(frappe.get_route(), ["List", "File", "List"]),

		//click integration icon (module)
		() => frappe.set_route(),
		() => frappe.tests.click_and_wait(icon('"Integrations"')),
		() => assert.deepEqual(frappe.get_route(), ["modules", "Integrations"]),
		() => done()
	]);
});

QUnit.skip("Test navbar notifications", function(assert) {
	assert.expect(2);
	let done = assert.async();
	let element_content;

	frappe.run_serially([
		() => frappe.tests.setup_doctype('ToDo'),
		() => frappe.set_route(),
		() => frappe.tests.click_and_wait('.navbar-new-comments-true'),                         ///******* need reload ********///
		() => element_content = $('ul#dropdown-notification li:nth-child(1) > a')[0].innerText,
		() => frappe.tests.click_and_wait('ul#dropdown-notification li:nth-child(1) > a'),
		() => {
			//check route
			assert.deepEqual(['List', 'ToDo', 'List'], frappe.get_route());
			//check number of elements
			assert.equal(cur_list.data.length, element_content.replace(/[^0-9]/gi, ''));
		},
		() => done()
	]);
});