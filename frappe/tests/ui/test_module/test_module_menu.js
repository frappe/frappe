QUnit.module('views');

QUnit.test("Test sidebar menu [Module view]", function(assert) {
	assert.expect(2);
	let done = assert.async();
	let sidebar_opt = '.module-link:not(".active")';
	let random_num;
	let module_name;

	frappe.run_serially([
		//testing click on module name in side bar
		() => frappe.set_route(['modules']),
		() => frappe.timeout(1),
		() => assert.deepEqual(['modules'], frappe.get_route(), "Module view opened successfully."),
		() => {
			//randomly choosing one module (not active)
			var count = $(sidebar_opt).length;
			random_num = Math.floor(Math.random() * (count) + 1);
			module_name = $(sidebar_opt)[random_num].innerText;
		},
		() => frappe.tests.click_and_wait(sidebar_opt, random_num),
		() => frappe.timeout(2),
		() => assert.equal($('.title-text:visible')[0].innerText, module_name, "Module opened successfully using sidebar"),
		() => done()
	]);
});
