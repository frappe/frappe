QUnit.module('views');

QUnit.test("List a document type", function(assert) {
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
		() => $('#navbar-search').val('customer'),
		() => $('#navbar-search').focus(),
		() => frappe.timeout(1),
		() => {
			assert.ok(frappe.tests.is_visible("Search for 'customer'"), "'Search for 'customer'' is visible!");
			if (frappe.tests.is_visible("Search for 'customer'")){
				let search_options = options();
				// Iterate over all available options till you reach "Search for 'customer'""
				for (option_number=0; option_number<search_options.length; option_number++)
					if ($(search_options[option_number]).text().includes("Search for 'customer'"))
						break;
			}
		},
		// Highlight the "Search for 'customer'" option
		() => awesome_search.awesomplete.goto(option_number),
		// Click the highlighted option
		() => awesome_search.awesomplete.select(),
		() => frappe.timeout(1),
		// Verify if the modal is correct
		() => assert.ok(frappe.tests.is_visible('Customer will have a table tabCustomer associated with it', 'p'), "Correct modal for 'customer' was called"),
		() => frappe.timeout(1),
		() => frappe.tests.close_modal(),

		() => done()
	]);
});