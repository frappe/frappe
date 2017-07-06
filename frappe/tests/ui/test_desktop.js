QUnit.module('views');

QUnit.test("Verification of navbar menu links", function(assert) {
	assert.expect(14);
	let done = assert.async();
	let navbar_user_items = ['Set Desktop Icons', 'My Settings', 'Reload', 'View Website', 'Background Jobs', 'Logout'];
	let modal_and_heading = [
		['Documentation', ['Documentation', 'span']],
		['About', ['Frappe Framework', 'div']]
	];
	
	frappe.run_serially([
		// Goto Home using button click to check if its working
		() => frappe.tests.click_navbar_item('Home'),
		() => assert.deepEqual([""], frappe.get_route()),

		// Click navbar-username and verify visibility of all elements 
		() => frappe.tests.click_navbar_item('navbar_user'),
		() => navbar_user_items.forEach(function(navbar_user_item) {
			assert.ok(frappe.tests.is_visible(navbar_user_item));
		}),

		() => frappe.tests.click_navbar_item('Help'),
		() => modal_and_heading.forEach(function(modal, index) {
			assert.ok(frappe.tests.is_visible(modal[0]));
		}),
		() => frappe.tests.click_navbar_item('Home'),
		() => frappe.timeout(0.3),

		// Click navbar-username and verify links of all menu items
		() => frappe.tests.click_navbar_item('navbar_user'),
		() => frappe.tests.click_navbar_user_item('Set Desktop Icons'),
		() => assert.deepEqual(["modules_setup"], frappe.get_route()),
		() => frappe.tests.click_navbar_item('Home'),

		() => frappe.tests.click_navbar_item('navbar_user'),
		() => frappe.tests.click_navbar_user_item('My Settings'),
		() => assert.deepEqual(["Form", "User", "Administrator"], frappe.get_route()),
		() => frappe.tests.click_navbar_item('Home'),

		() => frappe.tests.click_navbar_item('navbar_user'),
		() => frappe.tests.click_navbar_user_item('Background Jobs'),
		() => assert.deepEqual(["background_jobs"], frappe.get_route()),
		() => frappe.tests.click_navbar_item('Home'),

		// Click Help and check both modals
		() => frappe.tests.click_navbar_item('Help'),
		() => frappe.tests.click_navbar_help_item('Documentation'),
		() => assert.ok(frappe.tests.is_visible('Documentation', 'span')),
		() => frappe.tests.click_generic_text('Close', 'button'),

		() => frappe.tests.click_navbar_item('Help'),
		() => frappe.tests.click_navbar_help_item('About'),
		() => assert.ok(frappe.tests.is_visible('Frappe Framework', 'div')),
		() => frappe.tests.click_generic_text('Close', 'button'),

		() => done()
	]);
});