QUnit.module('views');

QUnit.test("Test Menu actions", function(assert) {
	assert.expect(8);//total 9
	let done = assert.async();
	let menu_button = '.menu-btn-group .dropdown-toggle';
	function dropdown_click(col) {
		return ('a:contains('+col+'):visible');
	}

	frappe.run_serially([
		// () => frappe.tests.setup_doctype('User'),
		() => frappe.tests.create_todo(2),

		//1. test Import
		() => frappe.set_route('List', 'ToDo', 'List'),
		() => frappe.timeout(1),
		() => frappe.tests.click_and_wait(menu_button, 1),
		() => frappe.tests.click_and_wait(dropdown_click('Import')),
		() => assert.deepEqual(frappe.get_route(), ["data-import-tool"], "Clicking Import worked correctly."),
		
		//2. test User Permissions Manager
		() => frappe.set_route('List', 'ToDo', 'List'),
		() => frappe.timeout(1),
		() => frappe.tests.click_and_wait(menu_button, 1),
		() => frappe.tests.click_and_wait(dropdown_click('User Permissions Manager')),
		() => assert.deepEqual(frappe.get_route(), ["user-permissions"], "Clicking User Permissions Manager worked correctly."),

		//3. test Role Permissions Manager
		() => frappe.set_route('List', 'ToDo', 'List'),
		() => frappe.timeout(1),
		() => frappe.tests.click_and_wait(menu_button, 1),
		() => frappe.tests.click_and_wait(dropdown_click('Role Permissions Manager')),
		() => assert.deepEqual(frappe.get_route(), ["permission-manager"], "Clicking Role Permissions Manager worked correctly."),

		//4. test Customize
		() => frappe.set_route('List', 'ToDo', 'List'),
		() => frappe.timeout(1),
		() => frappe.tests.click_and_wait(menu_button, 1),
		() => frappe.tests.click_and_wait(dropdown_click('Customize')),
		() => frappe.timeout(1),
		() => assert.deepEqual(frappe.get_route(), ["Form", "Customize Form"], "Clicking Customize worked correctly."),
		
		//5. test Assign To
		() => frappe.set_route('List', 'ToDo', 'List'),
		() => frappe.timeout(1),
		() => frappe.tests.click_and_wait('div:nth-child(1)>div>div>.list-row-checkbox'),
		() => frappe.timeout(1),
		() => frappe.tests.click_and_wait(menu_button, 1),
		() => frappe.tests.click_and_wait(dropdown_click('Assign To')),
		() => {
			assert.equal(cur_dialog.title, 'Add to To Do', "Dialog opened to assign todo.");
			cur_dialog.fields_dict.myself.$input[0].click();
		},
		() => frappe.timeout(0.5),
		() => cur_dialog.set_value('description', 'Assigned to me todo'),
		() => cur_dialog.primary_action(frappe.confirm),
		() => frappe.timeout(1),
		() => assert.equal(cur_list.data[0].description, 'Assigned to me todo', "Assigned todo exist in list."),
		
		//6. test Print
		() => frappe.set_route('List', 'ToDo', 'List'),
		() => frappe.timeout(1),
		() => frappe.tests.click_and_wait('div:nth-child(2)>div>div>.list-row-checkbox'),
		() => frappe.timeout(1),
		() => frappe.tests.click_and_wait(menu_button, 1),
		() => frappe.tests.click_and_wait(dropdown_click('Print')),
		() => {
			assert.equal(cur_dialog.title, 'Print Documents', "Dialog for print document opens.");
			$('button.btn-modal-close:visible').click();
		},
		
		// //7. test Add to Desktop
		// () => frappe.set_route("modules_setup"),
		// () => {
		// 	if ($('label:contains("ToDo")').is(':visible'))
		// 	{
		// 		$('label:contains("ToDo") > input').click();
		// 		$('.primary-action').click();
		// 	}
		// },
		// () => frappe.set_route('List', 'ToDo', 'List'),
		// () => frappe.tests.click_and_wait(menu_button, 1),
		// () => frappe.tests.click_and_wait(dropdown_click('Add to Desktop')),

		//*********************************************************************
		//  after setting icons it needs reload to show those icons on desk.
		//*********************************************************************

		// () => frappe.set_route("modules_setup"),
		// () => assert.ok($('label:contains("ToDo")').is(':visible'), "Added icon is visible on desk."),
		
		//8. test Edit DocType
		() => frappe.set_route('List', 'ToDo', 'List'),
		() => frappe.timeout(1),
		() => frappe.tests.click_and_wait(menu_button, 1),
		() => frappe.tests.click_and_wait(dropdown_click('Edit DocType')),
		() => assert.deepEqual(frappe.get_route(), ["Form", "DocType", "ToDo"], "Clicking Edit doctype worked correctly."),
		
		() => done()
	]);
});