// Copyright (c) 2017, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Test Runner', {
	refresh: (frm) => {
		frm.disable_save();
		frm.page.set_primary_action(__("Run Tests"), () => {
			let wrapper = $(frm.fields_dict.output.wrapper).empty();
			$("<div id='qunit'></div>").appendTo(wrapper);

			if(frm.doc.module_path) {
				// specific test
				frm.events.run_tests(frm, [frm.doc.module_path]);
			} else {
				// all tests
				frappe.call({
					method: 'frappe.core.doctype.test_runner.test_runner.get_all_tests'
				}).then((data) => {
					frm.events.run_tests(frm, data.message);
				});
			}
		});

	},
	run_tests: function(frm, files) {

		let require_list = [
			"assets/frappe/js/lib/jquery/qunit.js",
			"assets/frappe/js/lib/jquery/qunit.css"
		].concat(files);

		frappe.require(require_list, () => {
			QUnit.load();
			QUnit.done(() => {
				frappe.set_route('Form', 'Test Runner', 'Test Runner');
			});
		});

	}
});
