QUnit.module('views');

QUnit.test("Make a new record", function(assert) {
	assert.expect(3);
	let done = assert.async();
	let option_number=0;
	let awesome_search = $('#navbar-search').get(0);
	let random_text = frappe.utils.get_random(10);
	let options = () => {
		// Method to return the available options after search   
		return $('body > div.main-section > header > div > div > div.hidden-xs > form > div > div > ul > li').each(function (){});
	};
	let todo_title_text = () => {
		// Method to return the title of the todo visible  
		return $("div.list-item__content.ellipsis.list-item__content--flex-2 > a:visible").text();
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
			assert.ok(frappe.tests.is_visible('New ToDo'), "'New ToDo' is visible!");
			if (frappe.tests.is_visible('New ToDo')){
				let search_options = options();
				// Iterate over all available options till you reach 'New ToDo'
				for (option_number=0; option_number<search_options.length; option_number++)
					if ($(search_options[option_number]).text().includes('New ToDo'))
						break;
			}
		},
		// Highlight the 'New ToDo' option
		() => awesome_search.awesomplete.goto(option_number),
		// Click the highlighted option
		() => awesome_search.awesomplete.select(),
		() => frappe.timeout(1),
		() => frappe.quick_entry.dialog.set_value('description', random_text),
		() => frappe.quick_entry.insert(),
		() => frappe.timeout(1),
		() => frappe.set_route(["List", "ToDo", "List"]),
		() => frappe.timeout(1),
		// Verify if the todo is created
		() => frappe.tests.click_page_head_item("Refresh"),
		() => frappe.timeout(1),
		() => assert.ok(todo_title_text().includes(random_text), "New ToDo was created successfully"),
		() => assert.deepEqual(["List", "ToDo", "List"], frappe.get_route(), "Successfully routed to 'ToDo List'"),

		() => done()
	]);
});