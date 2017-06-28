// Copyright (c) 2017, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Test Runner', {
	refresh: (frm) => {
		frm.disable_save();
		frm.page.set_primary_action(__("Run Tests"), () => {
			return new Promise((resolve) => {
				let wrapper = $(frm.fields_dict.output.wrapper).empty();
				$("<div id='qunit'></div>").appendTo(wrapper);

				if(frm.doc.module_path) {
					// specific test
					frm.events.run_tests(frm, [frm.doc.module_path]);
					resolve();
				} else {
					// all tests
					frappe.call({
						method: 'frappe.core.doctype.test_runner.test_runner.get_all_tests'
					}).always((data) => {
						frm.events.run_tests(frm, data.message);
						resolve();
					});
				}
			});
		});

	},
	run_tests: function(frm, files) {
		let require_list = [
			"assets/frappe/js/lib/jquery/qunit.js",
			"assets/frappe/js/lib/jquery/qunit.css"
		].concat();

		frappe.require(require_list, () => {
			files.forEach((f) => {
				frappe.dom.eval(f.script);
			});

			QUnit.testDone(function(details) {
				var result = {
					"Module name": details.module,
					"Test name": details.name,
					"Assertions": {
						"Total": details.total,
						"Passed": details.passed,
						"Failed": details.failed
					},
					"Skipped": details.skipped,
					"Todo": details.todo,
					"Runtime": details.runtime
				};

				// eslint-disable-next-line
				console.log(JSON.stringify(result, null, 2));
			});
			QUnit.load();
			QUnit.done(() => {
				frappe.set_route('Form', 'Test Runner', 'Test Runner');
			});
		});

	}
});
