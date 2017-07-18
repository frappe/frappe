QUnit.module('views');

QUnit.test("Test Menu actions", function(assert) {
	assert.expect(7);//total 8
	let done = assert.async();
	let menu_button = '.menu-btn-group .dropdown-toggle:visible';
	function dropdown_click(col) {
		return ('a:contains('+col+'):visible');
	}

	frappe.run_serially([
		() => frappe.tests.setup_doctype('User'),
		() => frappe.tests.create_todo(2),

		//1. test Import
		() => frappe.set_route('List', 'ToDo', 'List'),
		() => frappe.timeout(1),
		() => frappe.tests.click_and_wait(menu_button),
		() => frappe.tests.click_and_wait(dropdown_click('Import')),
		() => assert.deepEqual(frappe.get_route(), ["data-import-tool"], "Clicking Import worked correctly."),
		
		//2. test User Permissions Manager
		() => frappe.set_route('List', 'ToDo', 'List'),
		() => frappe.timeout(1),
		() => frappe.tests.click_and_wait(menu_button),
		() => frappe.tests.click_and_wait(dropdown_click('User Permissions Manager')),
		() => assert.deepEqual(frappe.get_route(), ["user-permissions"], "Clicking User Permissions Manager worked correctly."),

		//3. test Role Permissions Manager
		() => frappe.set_route('List', 'ToDo', 'List'),
		() => frappe.timeout(1),
		() => frappe.tests.click_and_wait(menu_button),
		() => frappe.tests.click_and_wait(dropdown_click('Role Permissions Manager')),
		() => assert.deepEqual(frappe.get_route(), ["permission-manager"], "Clicking Role Permissions Manager worked correctly."),

		//4. test Customize
		() => frappe.set_route('List', 'ToDo', 'List'),
		() => frappe.timeout(1),
		() => frappe.tests.click_and_wait(menu_button),
		() => frappe.tests.click_and_wait(dropdown_click('Customize')),
		() => frappe.timeout(1),
		() => assert.deepEqual(frappe.get_route(), ["Form", "Customize Form"], "Clicking Customize worked correctly."),
		
		//5. test Edit DocType
		() => frappe.set_route('List', 'ToDo', 'List'),
		() => frappe.timeout(1),
		() => frappe.tests.click_and_wait(menu_button),
		() => frappe.tests.click_and_wait(dropdown_click('Edit DocType')),
		() => assert.deepEqual(frappe.get_route(), ["Form", "DocType", "ToDo"], "Clicking Edit doctype worked correctly."),

		//6. test Assign To
		() => frappe.set_route('List', 'ToDo', 'List'),
		() => frappe.timeout(0.5),
		() => frappe.tests.click_and_wait('div:nth-child(1)>div>div>.list-row-checkbox'),
		() => frappe.timeout(1),
		() => frappe.tests.click_and_wait(menu_button),
		() => frappe.tests.click_and_wait(dropdown_click('Assign To')),
		() => frappe.timeout(0.5),
		() => {
			assert.equal(cur_dialog.title, 'Add to To Do', "Dialog opened to assign todo.");
			$('button.btn-modal-close:visible').click();
		},
		
		//7. test Print
		() => frappe.set_route('List', 'ToDo', 'List'),
		() => frappe.timeout(0.5),
		() => frappe.tests.click_and_wait('div:nth-child(2)>div>div>.list-row-checkbox'),
		() => frappe.timeout(1),
		() => frappe.tests.click_and_wait(menu_button),
		() => frappe.tests.click_and_wait(dropdown_click('Print')),
		() => frappe.timeout(0.5),
		() => {
			assert.equal(cur_dialog.title, 'Print Documents', "Dialog for print document opens.");
			$('button.btn-modal-close:visible').click();
		},
		
		//8. test Add to Desktop
		// () => frappe.set_route("modules_setup"),
		// () => {
		// 	if ($('label:contains("ToDo")').is(':visible'))
		// 	{
		// 		$('label:contains("ToDo") > input').click();
		// 		$('.primary-action').click();
		// 	}
		// },
		// () => frappe.set_route('List', 'ToDo', 'List'),
		// () => frappe.tests.click_and_wait(menu_button),
		// () => frappe.tests.click_and_wait(dropdown_click('Add to Desktop')),

		// *********************************************************************
		//  after setting icons it needs reload to show those icons on desk.
		// *********************************************************************

		// () => frappe.set_route("modules_setup"),
		// () => assert.ok($('label:contains("ToDo")').is(':visible'), "Added icon is visible on desk."),
				
		() => done()
	]);
});