frappe.tests = {
	data: {},
	get_fixture_names: (doctype) => {
		return Object.keys(frappe.test_data[doctype]);
	},
	make: function(doctype, data) {
		return frappe.run_serially([
			() => frappe.set_route('List', doctype),
			() => frappe.new_doc(doctype),
			() => {
				if (frappe.quick_entry)
				{
					frappe.quick_entry.dialog.$wrapper.find('.edit-full').click();
					return frappe.timeout(1);
				}
			},
			() => {
				return frappe.tests.set_form_values(cur_frm, data);
			},
			() => frappe.timeout(1),
			() => (frappe.quick_entry ? frappe.quick_entry.insert() : cur_frm.save())
		]);
	},
	set_form_values: (frm, data) => {
		let tasks = [];

		data.forEach(item => {
			for (let key in item) {
				let task = () => {
					let value = item[key];
					if ($.isArray(value)) {
						return frappe.tests.set_grid_values(frm, key, value);
					} else {
						// single value
						return frm.set_value(key, value);
					}
				};
				tasks.push(task);
				tasks.push(() => frappe.timeout(0.2));
			}
		});

		// set values
		return frappe.run_serially(tasks);

	},
	set_grid_values: (frm, key, value) => {
		// set value in grid
		let grid = frm.get_field(key).grid;
		grid.remove_all();

		let grid_row_tasks = [];

		// build tasks for each row
		value.forEach(d => {
			grid_row_tasks.push(() => {
				grid.add_new_row();
				let grid_row = grid.get_row(-1).toggle_view(true);
				let grid_value_tasks = [];

				// build tasks to set each row value
				d.forEach(child_value => {
					for (let child_key in child_value) {
						grid_value_tasks.push(() => {
							return frappe.model.set_value(grid_row.doc.doctype,
								grid_row.doc.name, child_key, child_value[child_key]);
						});
						grid_value_tasks.push(() => frappe.timeout(0.2));
					}
				});

				return frappe.run_serially(grid_value_tasks);
			});
		});
		return frappe.run_serially(grid_row_tasks);
	},
	setup_doctype: (doctype) => {
		return frappe.run_serially([
			() => frappe.set_route('List', doctype),
			() => frappe.timeout(1),
			() => {
				frappe.tests.data[doctype] = [];
				let expected = frappe.tests.get_fixture_names(doctype);
				cur_list.data.forEach((d) => {
					frappe.tests.data[doctype].push(d.name);
					if(expected.indexOf(d.name) !== -1) {
						expected[expected.indexOf(d.name)] = null;
					}
				});

				let tasks = [];

				expected.forEach(function(d) {
					if(d) {
						tasks.push(() => frappe.tests.make(doctype,
							frappe.test_data[doctype][d]));
					}
				});

				return frappe.run_serially(tasks);
			}]);
	},
	click_and_wait: (button, obj=0.1) => {
		return frappe.run_serially([
			() => {
				//check if obj value is passed
				if (obj == 0.1)
					$(button).click();
				else
					$(button)[obj].click();
			},
			() => frappe.timeout(0.5)
		]);
	},
	create_todo: (todo_needed) => {
		let status_list = ['Closed', 'Open'];
		let priority_list = ['Low', 'Medium', 'High'];
		let date_list = ['2017-05-05', '2017-06-06', '2017-07-07', '2017-08-08'];
		let owner_list = ['Administrator', 'user1@mail.com'];
		let i;
		let num_of_todo;
		let tasks = [];

		return frappe.run_serially([
			() => frappe.set_route('List', 'ToDo', 'List'),
			() => {
				//remove todo filters
				for (i=1; i<=5; i++)
					$('.col-md-2:nth-child('+i+') .input-sm').val('');
			},
			() => cur_list.page.btn_secondary.click(),
			() => frappe.timeout(0.5),
			() => num_of_todo = cur_list.data.length,//todo present
			() => {
				if (num_of_todo < todo_needed)
				{
					for (i=0; i<(todo_needed-num_of_todo); i+=1)
					{
						tasks.push(() => frappe.tests.make("ToDo", [
							{description: 'ToDo for testing'},
							{status: status_list[i%2]},
							{priority: priority_list[i%3]},
							{date: date_list[i%4]},
							{owner: owner_list[i%2]}
						]));
						tasks.push(() => i+=1);
					}
					i=0;
				}
			},
			() => frappe.run_serially(tasks)
		]);
	},
	click_page_head_item: (text) => {
		// Method to items present on the page header like New, Save, Delete etc.
		let  possible_texts = ["New", "Delete", "Save", "Yes"];
		return frappe.run_serially([
			() => {
				if (text == "Menu"){
					$(`span.menu-btn-group-label:contains('Menu'):visible`).click();
				} else if (text == "Refresh") {
					$(`.btn-secondary:contains('Refresh'):visible`).click();
				} else if (possible_texts.includes(text)) {
					$(`.btn-primary:contains("${text}"):visible`).click();
				}
			},
			() => frappe.timeout(1)
		]);
	},
	click_dropdown_item: (text) => {
		// Method to click dropdown elements
		return frappe.run_serially([
			() => {
				let li = $(`.dropdown-menu li:contains("${text}"):visible`).get(0);
				$(li).find(`a`)[0].click();
			},
			() => frappe.timeout(1)
		]);
	},
	click_navbar_item: (text) => {
		// Method to click an elements present on the navbar
		return frappe.run_serially([
			() => {
				if (text == "Help"){
					$(`.dropdown-help .dropdown-toggle:visible`).click();
				}
				else if (text == "navbar_user"){
					$(`.dropdown-navbar-user .dropdown-toggle:visible`).click();
				}
				else if (text == "Notification"){
					$(`.navbar-new-comments`).click();
				}
				else if (text == "Home"){
					$(`.erpnext-icon`).click();
				}
			},
			() => frappe.timeout(1)
		]);
	},
	click_generic_text: (text, tag='a') => {
		// Method to click an element by its name
		return frappe.run_serially([
			() => $(`${tag}:contains("${text}"):visible`)[0].click(),
			() => frappe.timeout(1)
		]);
	},
	click_desktop_icon: (text) => {
		// Method to click the desktop icons on the Desk, by their name
		return frappe.run_serially([
			() => $("#icon-grid > div > div.app-icon[title="+text+"]").click(),
			() => frappe.timeout(1)
		]);
	},
	is_visible: (text, tag='a') => {
		// Method to check the visibility of an element
		return $(`${tag}:contains("${text}")`).is(`:visible`);
	},
	close_modal: () => {
		// Close the modal on the screen
		$(`a.close`).click();
	},
	click_print_logo: () => {
		return frappe.run_serially([
			() => $(`.fa-print`).click(),
			() => frappe.timeout(1)
		]);
	},
	click_button: function(text) {
		$(`.btn:contains("${text}"):visible`).click();
		return frappe.timeout(1);
	},
	click_link: function(text) {
		$(`a:contains("${text}"):visible`).click();
		return frappe.timeout(1);
	}
};