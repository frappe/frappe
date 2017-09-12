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
				tasks.push(frappe.after_ajax);
				tasks.push(() => frappe.timeout(0.4));
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

				let grid_value_tasks = [];
				grid_value_tasks.push(() => grid.add_new_row());
				grid_value_tasks.push(() => grid.get_row(-1).toggle_view(true));
				grid_value_tasks.push(() => frappe.timeout(0.5));

				// build tasks to set each row value
				d.forEach(child_value => {
					for (let child_key in child_value) {
						grid_value_tasks.push(() => {
							let grid_row = grid.get_row(-1);
							return frappe.model.set_value(grid_row.doc.doctype,
								grid_row.doc.name, child_key, child_value[child_key]);
						});
						grid_value_tasks.push(frappe.after_ajax);
						grid_value_tasks.push(() => frappe.timeout(0.4));
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
				$(li).find(`a`).click();
			},
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
	/**
	 * Clicks a button on a form.
	 * @param {String} text - The button's text
	 * @return {frappe.timeout}
	 * @throws will throw an exception if a matching visible button is not found
	 */
	click_button: function(text) {
		let element = $(`.btn:contains("${text}"):visible`);
		if(!element.length) {
			throw `did not find any button containing ${text}`;
		}
		element.click();
		return frappe.timeout(0.5);
	},
	/**
	 * Clicks a link on a form.
	 * @param {String} text - The text of the link to be clicked
	 * @return {frappe.timeout}
	 * @throws will throw an exception if a link with the given text is not found
	 */
	click_link: function(text) {
		let element = $(`a:contains("${text}"):visible`);
		if(!element.length) {
			throw `did not find any link containing ${text}`;
		}
		element.get(0).click();
		return frappe.timeout(0.5);
	},
	/**
	 * Sets the given control to the value given.
	 * @param {String} fieldname - The Doctype's field name
	 * @param {String} value - The value the control should be changed to
	 * @return {frappe.timeout}
	 * @throws will throw an exception if the field is not found or is not visible
	 */
	set_control: function(fieldname, value) {
		let control = $(`.form-control[data-fieldname="${fieldname}"]:visible`);
		if(!control.length) {
			throw `did not find any control with fieldname ${fieldname}`;
		}
		control.val(value).trigger('change');
		return frappe.timeout(0.5);
	},
	/**
	 * Checks if given field is disabled.
	 * @param {String} fieldname - The Doctype field name
	 * @return {Boolean} true if condition is met
	 * @throws will throw an exception if the field is not found or is not a form control
	 */
	is_disabled_field: function(fieldname){
		let control = $(`.form-control[data-fieldname="${fieldname}"]:disabled`);
		if(!control.length) {
			throw `did not find any control with fieldname ${fieldname}`;
		} else {
			return true;
		}
	}
};