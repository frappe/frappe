QUnit.module('views');

QUnit.test("Search in a document type", function(assert) {
	assert.expect(3);
	let done = assert.async();
	let option_number=0;
	let awesome_search = $('#navbar-search').get(0);
	let random_text = "argo1234";
	let options = () => {
		// Method to return the available options after search   
		return $('body > div.main-section > header > div > div > div.hidden-xs > form > div > div > ul > li').each(function (){});
	};
	let todo_title_text = () => {
		// Method to return the title of the todo visible  
		return $("div.list-item__content.ellipsis.list-item__content--flex-2 > a:visible").text();
	};
	let select_all_todo = () => {
		$('div.list-item__content.ellipsis.text-muted.list-item__content--flex-2 > input:visible').click();
	};
	let remove_all_filters = () => {
		$('button.remove-filter > i').click();
	};

	frappe.run_serially([
		// Goto Home using button click to check if its working
		() => frappe.set_route(),
		() => frappe.timeout(0.3),

		() => $('#navbar-search').focus(),
		() => $('#navbar-search').val('ToDo'),
		() => $('#navbar-search').focus(),
		() => frappe.timeout(0.3),
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
		() => frappe.timeout(0.5),

		// Search for the created ToDo in global search
		() => frappe.set_route(["List", "ToDo", "List"]),
		() => frappe.timeout(1),
		() => $('#navbar-search').focus(),
		() => $('#navbar-search').val('argo1234'),
		() => $('#navbar-search').focus(),
		() => frappe.timeout(0.3),
		() => {
			assert.ok(frappe.tests.is_visible('Find argo1234 in ToDo'), "'Find argo1234 in ToDo' is visible!");
			if (frappe.tests.is_visible('Find argo1234 in ToDo')){
				let search_options = options();
				// Iterate over all available options till you reach 'New ToDo'
				for (option_number=0; option_number<search_options.length; option_number++)
					if ($(search_options[option_number]).text().includes('Find argo1234 in ToDo'))
						break;
			}
		},
		// Highlight the 'Find argo1234 in ToDo' option
		() => awesome_search.awesomplete.goto(option_number),
		// Click the highlighted option
		() => awesome_search.awesomplete.select(),
		() => frappe.timeout(1),
		// Verify if the 'argo1234' is the only ToDo
		() => assert.ok(todo_title_text().includes('argo1234'), "'argo1234' is the only visible ToDo"),

		// Remove all filters
		() => remove_all_filters(),
		() => frappe.timeout(0.3),
		// Delete all ToDo
		() => select_all_todo(),
		() => frappe.timeout(0.3),
		() => frappe.tests.click_page_head_item('Delete'),
		() => frappe.tests.click_page_head_item('Yes'),

		() => done()
	]);
});