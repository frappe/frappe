QUnit.module('listView');

QUnit.test("test quick entry", function(assert) {
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

QUnit.test("test list values", function(assert) {
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

QUnit.test("test fliters", function(assert) {
	assert.expect(2);
	let done = assert.async();
	//to select filter randomly 
	let textArray = ['Open', 'Closed'];
	let randomNumber = Math.floor(Math.random()*textArray.length);

	frappe.run_serially([
		() => frappe.tests.setup_doctype('ToDo'),
		() => frappe.set_route('List', 'ToDo'),
		() => {
			assert.deepEqual(['List', 'ToDo', 'List'], frappe.get_route());
			$('.col-md-2 > .input-sm').val(textArray[randomNumber]);
		},
		() => frappe.timeout(1),
		() => $('.btn-sm.hidden-xs .hidden-xs').click(),
		() => frappe.timeout(1),
		() => {
			//get total list element
			var count = cur_list.data.length;
			//check if all elements are as per filter
			var i=0;
			for ( ; i < count ; i++)
				if ( cur_list.data[i].status != textArray[randomNumber] )
					break;

			assert.ok( i==count );
		},
		() => done()
	]);
});

QUnit.test("test deletion of one list element", function(assert) {
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
			cur_list.$page.find('div:nth-child('+random+')>div>div>.list-row-checkbox').click();
		},
		() => $('.btn-danger').click(),
		() => frappe.timeout(1),
		() => {
			//check if asking for confirmation and click yes
			assert.deepEqual("Confirm", cur_dialog.title);
			cur_dialog.primary_action(frappe.confirm);
		},
		() => frappe.timeout(1),
		() => assert.ok( cur_list.data.length == (count-1) ),
		() => done()
	]);
});

QUnit.test("test deletion of all list element", function(assert) {
	assert.expect(3);
	let done = assert.async();

	frappe.run_serially([
		() => frappe.tests.setup_doctype('ToDo'),
		() => frappe.set_route('List', 'ToDo'),
		() => {
			assert.deepEqual(['List', 'ToDo', 'List'], frappe.get_route());
			//select all element
			cur_list.$page.find('.list-select-all.hidden-xs').click();
		},
		() => $('.btn-danger').click(),
		() => frappe.timeout(1),
		() => {
			assert.deepEqual("Confirm", cur_dialog.title);
			//click yes for deletion
			cur_dialog.primary_action(frappe.confirm);
		},
		() => frappe.timeout(1),
		() => assert.ok( cur_list.data.length == 0 ),
		() => done()
	]);
});