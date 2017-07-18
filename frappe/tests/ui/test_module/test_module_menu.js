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
		() => assert.equal($('.title-text:visible')[0].innerText, module_name, "Module opened successfully using sidebar"),
		() => done()
	]);
});

QUnit.test("Test Menu button [Module view]", function(assert) {
	assert.expect(2);
	let done = assert.async();
	let menu_button = '.menu-btn-group .dropdown-toggle:visible';
	function dropdown_click(col) {
		return ('a:contains('+col+'):visible');
	}

	frappe.run_serially([

		//1. Test Set Desktop Icon
		() => frappe.set_route(['modules']),
		() => frappe.timeout(0.5),
		() => frappe.tests.click_and_wait(menu_button),
		() => frappe.tests.click_and_wait(dropdown_click('Set Desktop Icons')),
		() => assert.deepEqual(frappe.get_route(), ["modules_setup"], "Clicking Set Desktop Icons worked correctly."),
		
		//2. Test Install Apps		
		() => frappe.set_route(['modules']),
		() => frappe.timeout(0.5),
		() => frappe.tests.click_and_wait(menu_button),
		() => frappe.tests.click_and_wait(dropdown_click('Install Apps')),
		() => assert.deepEqual(frappe.get_route(), ["applications"], "Clicking Install Apps worked correctly."),

		() => done()
	]);
});