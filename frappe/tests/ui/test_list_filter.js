QUnit.module('views');

QUnit.test("Test filters", function(assert) {
	assert.expect(2);
	let done = assert.async();

	frappe.run_serially([
		() => frappe.tests.setup_doctype('User'),
		() => frappe.tests.create_todo(6),
		() => frappe.set_route('List', 'ToDo', 'List'),
		() => frappe.timeout(0.5),
		() => {
			assert.deepEqual(['List', 'ToDo', 'List'], frappe.get_route(), "List opened successfully.");
			//set filter values
			$('.col-md-2:nth-child(2) .input-sm').val('Closed');
			$('.col-md-2:nth-child(3) .input-sm').val('Low');
			$('.col-md-2:nth-child(4) .input-sm').val('05-05-2017');
			$('.col-md-2:nth-child(5) .input-sm').val('Administrator');
		},
		() => frappe.timeout(0.5),
		() => cur_list.page.btn_secondary.click(),
		() => frappe.timeout(1),
		() => {
			//get total list element
			var count = cur_list.data.length;
			//check if all elements are as per filter
			var i=0;
			for ( ; i < count ; i++)
				if ((cur_list.data[i].status!='Closed')||(cur_list.data[i].priority!='Low')||(cur_list.data[i].owner!='Administrator')||(cur_list.data[i].date!='2017-05-05'))
					break;
			assert.equal(count, i, "Elements present have content according to filters.");
		},
		() => done()
	]);
});

QUnit.log( ( { result, module, name, message, actual, expected, source } ) => {
	if ( result ) {
		return;
	}
	let output = `FAILED: ${module}: ${name}: `;

	if ( message ) {
		output += `${message}, `;
	}
	if ( actual ) {
		output += `expected: ${expected}, actual: ${actual}`;
	}
	if ( source ) {
		output += `, ${source}`;
	}
	console.log( output );
});