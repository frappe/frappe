QUnit.module('views');
// check all menu items and see if theyre all correct links

QUnit.test("Open a module or tool", function(assert) {
	assert.expect(2);
	let done = assert.async();
	let option_number=0;
	let awesome_search = $('#navbar-search').get(0);
	let options = () => {
		// Method to return the available options after search   
		return $('body > div.main-section > header > div > div > div.hidden-xs > form > div > div > ul > li').each(function (){}); // 'p' because the arbitrary time is pm 
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
		() => frappe.timeout(0.3),
		// Verify if the redirected route is correct
		() => assert.deepEqual(["List", "ToDo", "List"], frappe.get_route(), "Successfully routed to 'ToDo List'"),

		() => done()
	]);
});

QUnit.test("Make a new record", function(assert) {
	assert.expect(3);
	let done = assert.async();
	let option_number=0;
	let awesome_search = $('#navbar-search').get(0);
	let random_text = frappe.utils.get_random(10);
	let options = () => {
		// Method to return the available options after search   
		return $('body > div.main-section > header > div > div > div.hidden-xs > form > div > div > ul > li').each(function (){}); // 'p' because the arbitrary time is pm 
	};
	let todo_title_text = () => {
		// Method to return the title of the todo visible  
		return $("div.list-item__content.ellipsis.list-item__content--flex-2 > a:visible").text();
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
		() => frappe.set_route(["List", "ToDo", "List"]),
		() => frappe.timeout(1),
		// Verify if the todo is created
		() => frappe.tests.click_page_head_item("Refresh"),
		() => frappe.timeout(0.3),
		() => assert.ok(todo_title_text().includes(random_text), "New ToDo was created successfully"),
		() => assert.deepEqual(["List", "ToDo", "List"], frappe.get_route(), "Successfully routed to 'ToDo List'"),

		() => done()
	]);
});

QUnit.test("Search in a document type", function(assert) {
	assert.expect(3);
	let done = assert.async();
	let option_number=0;
	let awesome_search = $('#navbar-search').get(0);
	let random_text = "argo1234";
	let options = () => {
		// Method to return the available options after search   
		return $('body > div.main-section > header > div > div > div.hidden-xs > form > div > div > ul > li').each(function (){}); // 'p' because the arbitrary time is pm 
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

QUnit.test("List a document type", function(assert) {
	assert.expect(2);
	let done = assert.async();
	let option_number=0;
	let awesome_search = $('#navbar-search').get(0);
	let options = () => {
		// Method to return the available options after search   
		return $('body > div.main-section > header > div > div > div.hidden-xs > form > div > div > ul > li').each(function (){}); // 'p' because the arbitrary time is pm 
	};

	frappe.run_serially([
		// Goto Home using button click to check if its working
		() => frappe.set_route(),
		() => frappe.timeout(0.3),

		() => $('#navbar-search').focus(),
		() => $('#navbar-search').val('customer'),
		() => $('#navbar-search').focus(),
		() => frappe.timeout(0.3),
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


QUnit.test("Math Calculations", function(assert) {
	assert.expect(5);
	let done = assert.async();
	let awesome_search = $('#navbar-search').get(0);
	let random_number_1 = (Math.random()*100).toFixed(2);
	let random_number_2 = (Math.random()*100).toFixed(2);
	let operations = ['+', '-', '/', '*'];

	frappe.run_serially([
		// Goto Home using button click to check if its working
		() => frappe.set_route(),
		() => frappe.timeout(0.3),

		() => $('#navbar-search').focus(),
		() => $('#navbar-search').val(random_number_1+operations[0]+random_number_2),
		() => $('#navbar-search').focus(),
		() => frappe.timeout(0.3),
		() => {
			let num_str = random_number_1+operations[0]+random_number_2+' = '+parseFloat(parseFloat(random_number_1)+parseFloat(random_number_2));
			assert.ok(frappe.tests.is_visible(num_str), "Math operation '"+operations[0]+"' is correct");
		},

		() => $('#navbar-search').focus(),
		() => $('#navbar-search').val(random_number_1+operations[1]+random_number_2),
		() => $('#navbar-search').focus(),
		() => frappe.timeout(0.3),
		() => {
			let num_str = random_number_1+operations[1]+random_number_2+' = '+parseFloat(parseFloat(random_number_1)-parseFloat(random_number_2));
			assert.ok(frappe.tests.is_visible(num_str), "Math operation '"+operations[1]+"' is correct");
		},

		() => $('#navbar-search').focus(),
		() => $('#navbar-search').val(random_number_1+operations[2]+random_number_2),
		() => $('#navbar-search').focus(),
		() => frappe.timeout(0.3),
		() => {
			let num_str = random_number_1+operations[2]+random_number_2+' = '+parseFloat(parseFloat(random_number_1)/parseFloat(random_number_2));
			assert.ok(frappe.tests.is_visible(num_str), "Math operation '"+operations[2]+"' is correct");
		},

		() => $('#navbar-search').focus(),
		() => $('#navbar-search').val(random_number_1+operations[3]+random_number_2),
		() => $('#navbar-search').focus(),
		() => frappe.timeout(0.3),
		() => {
			let num_str = random_number_1+operations[3]+random_number_2+' = '+parseFloat(parseFloat(random_number_1)*parseFloat(random_number_2));
			assert.ok(frappe.tests.is_visible(num_str), "Math operation '"+operations[3]+"' is correct");
		},

		() => $('#navbar-search').focus(),
		() => $('#navbar-search').val("=Math.sin(Math.PI/2)"),
		() => $('#navbar-search').focus(),
		() => frappe.timeout(0.3),
		() => assert.ok(frappe.tests.is_visible("Math.sin(Math.PI/2) = 1"), "Math operation 'sin' evaluated correctly"),

		// Close the modal
		() => awesome_search.awesomplete.select(),
		() => frappe.tests.close_modal(),

		() => done()
	]);
});