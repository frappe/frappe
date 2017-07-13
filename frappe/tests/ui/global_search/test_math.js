QUnit.module('views');

QUnit.test("Math Calculations", function(assert) {
	assert.expect(5);
	let done = assert.async();
	let awesome_search = $('#navbar-search').get(0);
	let random_number_1 = (Math.random()*100).toFixed(2);
	let random_number_2 = (Math.random()*100).toFixed(2);
	let operations = ['+', '-', '/', '*'];

	frappe.run_serially([
		// Goto Home using button click to check if its working
		() => frappe.set_route(),
		() => frappe.timeout(0.3),

		() => $('#navbar-search').focus(),
		() => $('#navbar-search').val(random_number_1+operations[0]+random_number_2),
		() => $('#navbar-search').focus(),
		() => frappe.timeout(0.3),
		() => {
			let num_str = random_number_1+operations[0]+random_number_2+' = '+parseFloat(parseFloat(random_number_1)+parseFloat(random_number_2));
			assert.ok(frappe.tests.is_visible(num_str), "Math operation '"+operations[0]+"' is correct");
		},

		() => $('#navbar-search').focus(),
		() => $('#navbar-search').val(random_number_1+operations[1]+random_number_2),
		() => $('#navbar-search').focus(),
		() => frappe.timeout(0.3),
		() => {
			let num_str = random_number_1+operations[1]+random_number_2+' = '+parseFloat(parseFloat(random_number_1)-parseFloat(random_number_2));
			assert.ok(frappe.tests.is_visible(num_str), "Math operation '"+operations[1]+"' is correct");
		},

		() => $('#navbar-search').focus(),
		() => $('#navbar-search').val(random_number_1+operations[2]+random_number_2),
		() => $('#navbar-search').focus(),
		() => frappe.timeout(0.3),
		() => {
			let num_str = random_number_1+operations[2]+random_number_2+' = '+parseFloat(parseFloat(random_number_1)/parseFloat(random_number_2));
			assert.ok(frappe.tests.is_visible(num_str), "Math operation '"+operations[2]+"' is correct");
		},

		() => $('#navbar-search').focus(),
		() => $('#navbar-search').val(random_number_1+operations[3]+random_number_2),
		() => $('#navbar-search').focus(),
		() => frappe.timeout(0.3),
		() => {
			let num_str = random_number_1+operations[3]+random_number_2+' = '+parseFloat(parseFloat(random_number_1)*parseFloat(random_number_2));
			assert.ok(frappe.tests.is_visible(num_str), "Math operation '"+operations[3]+"' is correct");
		},

		() => $('#navbar-search').focus(),
		() => $('#navbar-search').val("=Math.sin(Math.PI/2)"),
		() => $('#navbar-search').focus(),
		() => frappe.timeout(0.3),
		() => assert.ok(frappe.tests.is_visible("Math.sin(Math.PI/2) = 1"), "Math operation 'sin' evaluated correctly"),

		// Close the modal
		() => awesome_search.awesomplete.select(),
		() => frappe.tests.close_modal(),

		() => done()
	]);
});