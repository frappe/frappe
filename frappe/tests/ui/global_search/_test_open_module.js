QUnit.module('views');

QUnit.test("Open a module or tool", function(assert) {
	assert.expect(2);
	let done = assert.async();
	let option_number=0;
	let awesome_search = $('#navbar-search').get(0);
	let options = () => {
		// Method to return the available options after search   
		return $('body > div.main-section > header > div > div > div.hidden-xs > form > div > div > ul > li').each(function (){});
	};

	frappe.run_serially([
		// Goto Home using button click to check if its working
		() => frappe.set_route(),
		() => frappe.timeout(1),

		() => $('#navbar-search').focus(),
		() => $('#navbar-search').val('ToDo'),
		() => $('#navbar-search').focus(),
		() => frappe.timeout(1),
		() => {
			assert.ok(frappe.tests.is_visible('ToDo List'), "'ToDo List' is visible!");
			if (frappe.tests.is_visible('ToDo List')){
				let search_options = options();
				// Iterate over all available options till you reach 'ToDo List'
				for (option_number=0; option_number<search_options.length; option_number++)
					if ($(search_options[option_number]).text().includes('ToDo List'))
						break;
			}
		},
		// Highlight the 'ToDo List' option
		() => awesome_search.awesomplete.goto(option_number),
		// Click the highlighted option
		() => awesome_search.awesomplete.select(),
		() => frappe.timeout(1),
		// Verify if the redirected route is correct
		() => assert.deepEqual(["List", "ToDo", "List"], frappe.get_route(), "Successfully routed to 'ToDo List'"),

		() => done()
	]);
});