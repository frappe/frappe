QUnit.module('setup');

QUnit.test("Test Workflow", function(assert) {
	assert.expect(1);
	let done = assert.async();

	frappe.run_serially([
		() => {
			return frappe.tests.make('Workflow', [
				{workflow_name: "Test User Workflow"},
				{document_type: "User"},
				{is_active: 1},
				{override_status: 1},
				{states: [
					[
						{state: 'Pending'},
						{doc_status: 0},
						{allow_edit: 'Administrator'}
					],
					[
						{state: 'Approved'},
						{doc_status: 1},
						{allow_edit: 'Administrator'}
					],
					[
						{state: 'Rejected'},
						{doc_status: 2},
						{allow_edit: 'Administrator'}
					]
				]},
				{transitions: [
					[
						{state: 'Pending'},
						{action: 'Review'},
						{next_state: 'Pending'},
						{allowed: 'Administrator'}
					],
					[
						{state: 'Pending'},
						{action: 'Approve'},
						{next_state: 'Approved'},
						{allowed: 'Administrator'}
					],
					[
						{state: 'Approved'},
						{action: 'Reject'},
						{next_state: 'Rejected'},
						{allowed: 'Administrator'}
					],
				]},
				{workflow_state_field: 'workflow_state'}
			]);
		},
		() => frappe.timeout(1),
		() => {assert.equal($('.msgprint').text(), "Created Custom Field workflow_state in User", "Workflow created");},	
		() => frappe.tests.click_button('Close'),
		() => done()
	]);
});