QUnit.test("test project", function(assert) {
	assert.expect(1);
	let done = assert.async();
	frappe.run_serially([
		() => {
			return frappe.tests.make('Project', [{
				project_name: 'Test App'
			}, {
				expected_start_date: '2017-07-22'
			}, {
				expected_start_date: '2017-09-22'
			}, {
				estimated_costing: '10,000.00'
			}]);
		},
		() => {
			assert.ok(cur_frm.project_name.includes('Test App'),
				'name correctly set');	
		},
		() => {
			frappe.timeout(2);
				return frappe.tests.make('Task', [{
					subject: 'Documentation'
				}, {
					project: 'Test App'
				}, {
					description: 'To make a proper documentation defining requirements etc'
				}]);
		},
		() => {
			frappe.timeout(2);
				return frappe.tests.make('Activity Type', [{
					activity_type: 'Planning'
				}, {
					billing_rate: '0.00'
				}, {
					costing_rate: '0.00'
				}]);
		},
		() => {
			frappe.timeout(2);
				return frappe.tests.make('Activity Cost', [{
					activity_type: 'Planning'
				}, {
					employee: 'EMP/0001'
				}]);
		},
		() => {
			//assert.ok(cur_frm.doc.subject=='Test App');
			//assert.ok(cur_frm.doc.status=='Lead');
		},
		() => done()
	]);
});

//bench --site Tests run-ui-tests --test erpnext/crm/doctype/lead/test_lead.js