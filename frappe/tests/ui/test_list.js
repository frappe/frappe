QUnit.module('views');

QUnit.skip("Test quick entry", function(assert) {
	assert.expect(2);
	let done = assert.async();
	let random = frappe.utils.get_random(10);

	frappe.run_serially([
		() => frappe.set_route('List', 'ToDo'),
		() => frappe.new_doc('ToDo'),
		() => frappe.quick_entry.dialog.set_value('description', random),
		() => frappe.quick_entry.insert(),
		(doc) => {
			assert.ok(doc && !doc.__islocal);
			return frappe.set_route('Form', 'ToDo', doc.name);
		},
		() => {
			assert.ok(cur_frm.doc.description.includes(random));
			return done();
		}
	]);
});

QUnit.skip("Test list values", function(assert) {
	assert.expect(2);
	let done = assert.async();

	frappe.run_serially([
		() => frappe.set_route('List', 'DocType'),
		() => {
			assert.deepEqual(['List', 'DocType', 'List'], frappe.get_route());
			assert.ok(cur_list.data.length > 10);
			done();
		}
	]);
});

QUnit.skip("Test Menu actions", function(assert) {
	assert.expect(1);//total 9
	let done = assert.async();
	let menu_button = '.menu-btn-group .dropdown-toggle';
	function dropdown_click(col) {
		return ('a:contains('+col+'):visible');
	}

	frappe.run_serially([
		() => frappe.tests.setup_doctype('ToDo'),

		//test Import
		() => frappe.set_route('List', 'ToDo'),
		() => frappe.tests.click_and_wait(menu_button),
		() => frappe.tests.click_and_wait(dropdown_click('Import')),
		() => assert.deepEqual(frappe.get_route(), ["data-import-tool"]),
		
		// //test User Permissions Manager
		// () => frappe.set_route('List', 'ToDo'),
		// () => frappe.tests.click_and_wait(menu_button),
		// () => frappe.tests.click_and_wait(dropdown_click('User Permissions Manager')),
		// () => assert.deepEqual(frappe.get_route(), ["user-permissions"]),

		// //test Role Permissions Manager
		// () => frappe.set_route('List', 'ToDo'),
		// () => frappe.tests.click_and_wait(menu_button),
		// () => frappe.tests.click_and_wait(dropdown_click('Role Permissions Manager')),
		// () => assert.deepEqual(frappe.get_route(), ["permission-manager"]),

		// //test Customize
		// () => frappe.set_route('List', 'ToDo'),
		// () => frappe.tests.click_and_wait(menu_button),
		// () => frappe.tests.click_and_wait(dropdown_click('Customize')),
		// () => assert.deepEqual(frappe.get_route(), ["Form", "Customize Form"]),
		
		// //test Print
		// () => frappe.set_route('List', 'ToDo'),
		// () => frappe.tests.click_and_wait('div:nth-child(1)>div>div>.list-row-checkbox'),
		// () => frappe.tests.click_and_wait(menu_button),
		// () => frappe.tests.click_and_wait(dropdown_click('Print')),
		// () => assert.equal(cur_dialog.title, 'Print Documents'),
		
		// //test Assign To
		// () => frappe.set_route('List', 'ToDo'),
		// () => frappe.tests.click_and_wait('div:nth-child(1)>div>div>.list-row-checkbox'),
		// () => frappe.tests.click_and_wait(menu_button),
		// () => frappe.tests.click_and_wait(dropdown_click('Assign To')),
		// () => {
		// 	assert.equal(cur_dialog.title, 'Add to To Do');
		// 	cur_dialog.fields_dict.myself.$input[0].click();
		// },
		// () => frappe.timeout(0.5),
		// () => {
		// 	cur_dialog.set_value('description', 'Assigned to me todo');
		// 	cur_dialog.primary_action(frappe.confirm);
		// },
		// () => frappe.timeout(1),
		// () => assert.equal(cur_list.data[0].description, 'Assigned to me todo'),
		
		// //test Add to Desktop
		// () => frappe.set_route("modules_setup"),
		// () => {
		// 	if ($('label:contains("ToDo")').is(':visible'))
		// 	{
		// 		$('label:contains("ToDo") > input').click();
		// 		$('.primary-action').click();
		// 	}
		// },
		// () => frappe.set_route('List', 'ToDo'),
		// () => frappe.tests.click_and_wait(menu_button),
		// () => frappe.tests.click_and_wait(dropdown_click('Add to Desktop')),
		// () => frappe.set_route("modules_setup"),                                    ///************* needs reload here ************///
		// () => assert.ok($('label:contains("ToDo")').is(':visible')),
		
		// //test Edit DocType
		// () => frappe.set_route('List', 'ToDo'),
		// () => frappe.tests.click_and_wait(menu_button),
		// () => frappe.tests.click_and_wait(dropdown_click('Edit DocType')),
		// () => assert.deepEqual(frappe.get_route(), ["Form", "DocType", "ToDo"]),
		
		() => done()
	]);
});

QUnit.skip("Test filters", function(assert) {
	assert.expect(2);
	let done = assert.async();

	frappe.run_serially([
		// () => frappe.tests.setup_doctype('User'),
		() => frappe.tests.setup_doctype('ToDo'),
		() => frappe.set_route('List', 'ToDo'),
		() => {
			assert.deepEqual(['List', 'ToDo', 'List'], frappe.get_route());
			$('.col-md-2:nth-child(2) .input-sm').val('Closed');
			$('.col-md-2:nth-child(3) .input-sm').val('Low');
			$('.col-md-2:nth-child(4) .input-sm').val('05-07-2017');
			$('.col-md-2:nth-child(5) .input-sm').val('Administrator');
		},
		() => frappe.timeout(1),
		() => cur_list.page.btn_secondary.click(),
		() => frappe.timeout(1),
		() => {
			//get total list element
			var count = cur_list.data.length;
			//check if all elements are as per filter
			var i=0;
			for ( ; i < count ; i++)
				if ((cur_list.data[i].status!='Closed')||(cur_list.data[i].priority!='Low')||(cur_list.data[i].owner!='Administrator')||(cur_list.data[i].date!='2017-07-05'))
					break;
			assert.equal(i, count);
		},
		() => done()
	]);
});

QUnit.skip("Test deletion of one list element", function(assert) {
	assert.expect(3);
	let done = assert.async();
	let count;
	let random;

	frappe.run_serially([
		() => frappe.tests.setup_doctype('ToDo'),
		() => frappe.set_route('List', 'ToDo'),
		() => {
			assert.deepEqual(['List', 'ToDo', 'List'], frappe.get_route());
			//total list elements
			count = cur_list.data.length;
			random = Math.floor(Math.random() * (count) + 1);
			//select one element randomly
			$('div:nth-child('+random+')>div>div>.list-row-checkbox').click();
		},
		() => cur_list.page.btn_primary.click(),
		() => frappe.timeout(0.5),
		() => {
			//check if asking for confirmation and click yes
			assert.equal("Confirm", cur_dialog.title);
			cur_dialog.primary_action(frappe.confirm);
		},
		() => frappe.timeout(1),
		() => assert.equal(cur_list.data.length, (count-1)),
		() => done()
	]);
});

QUnit.skip("Test deletion of all list element", function(assert) {
	assert.expect(3);
	let done = assert.async();

	frappe.run_serially([
		() => frappe.tests.setup_doctype('ToDo'),
		() => frappe.set_route('List', 'ToDo'),
		() => {
			assert.deepEqual(['List', 'ToDo', 'List'], frappe.get_route());
			//select all element
			$('.list-select-all.hidden-xs').click();
		},
		() => cur_list.page.btn_primary.click(),
		() => frappe.timeout(0.5),
		() => {
			assert.equal("Confirm", cur_dialog.title);
			//click yes for deletion
			cur_dialog.primary_action(frappe.confirm);
		},
		() => frappe.timeout(2),
		() => assert.equal( cur_list.data.length, '0' ),
		() => done()
	]);
});

QUnit.skip("Test paging in list", function(assert) {
	assert.expect(2);
	let done = assert.async();

	frappe.run_serially([
		() => frappe.tests.setup_doctype('ToDo'),
		() => frappe.set_route('List', 'ToDo'),
		() => {
			assert.deepEqual(['List', 'ToDo', 'List'], frappe.get_route());
			//remove all filters
			for (var i=1; i<=5; i++)
				$('.col-md-2:nth-child('+i+') .input-sm').val('');
		},
		() => frappe.timeout(1),
		() => cur_list.page.btn_secondary.click(),
		() => frappe.timeout(0.5),
		() => assert.ok(cur_list.data.length <= cur_list.page_length),
		() => done()
	]);
});