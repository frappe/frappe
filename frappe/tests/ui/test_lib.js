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
				let frm = frappe.quick_entry ? frappe.quick_entry.dialog : cur_frm;
				return frappe.tests.set_form_values(frm, data);
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
					}
				});

				return frappe.run_serially(grid_value_tasks);
			});
		});
		return frappe.run_serially(grid_row_tasks);
	},
	setup_doctype: (doctype) => {
		return frappe.set_route('List', doctype)
			.then(() => {
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
			});
	},
	click_page_head_item: (text) => {
		let  possible_texts = ["New", "Delete", "Save", "Yes"];
		return frappe.run_serially([
			() => {
				if (text == "Menu"){
					$("span.menu-btn-group-label:contains('Menu'):visible").click();
				} else if (text == "Refresh") {
					$(".btn-secondary:contains('Refresh'):visible").click();
				} else if (possible_texts.includes(text)) {
					$(".btn-primary:contains("+text+"):visible").click();
				}
			},
			() => frappe.timeout(0.3)
		]);
	},
	click_dropdown_item: (text) => {
		return frappe.run_serially([
			() => {
				let li = $(".dropdown-menu li:contains("+text+"):visible").get(0);
				$(li).find('a')[0].click();
			},
			() => frappe.timeout(0.3)
		]);
	},
	click_navbar_item: (text) => {
		return frappe.run_serially([
			() => {
				if (text == "Help"){
					$(".dropdown-help .dropdown-toggle:visible").click();
				}
				else if (text == "navbar_user"){
					$(".dropdown-navbar-user .dropdown-toggle:visible").click();
				}
				else if (text == "Notification"){
					$(".navbar-new-comments").click();
				}
				else if (text == "Home"){
					$(".navbar-home:contains('Home'):visible")[0].click();
				}
			},
			() => frappe.timeout(0.3)
		]);
	},
	click_generic_text: (text, tag='a') => {
		return frappe.run_serially([
			() => $(tag+":contains("+text+"):visible")[0].click(),
			() => frappe.timeout(0.3)
		]);
	},
	click_desktop_icon: (text) => {
		return frappe.run_serially([
			() => $("#icon-grid > div > div.app-icon[title="+text+"]").click(),
			() => frappe.timeout(0.3)
		]);
	},
	is_visible: (text, tag='a') => {
		return $(tag+":contains("+text+")").is(':visible');
	}
};