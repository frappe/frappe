QUnit.module('views');

QUnit.test("Verification of navbar menu links", function(assert) {
	assert.expect(14);
	let done = assert.async();
	let navbar_user_items = ['Set Desktop Icons', 'My Settings', 'Reload', 'View Website', 'Background Jobs', 'Logout'];
	let modal_and_heading = ['Documentation', 'About'];

	frappe.run_serially([
		// Goto Desk using button click to check if its working
		() => frappe.tests.click_navbar_item('Home'),
		() => assert.deepEqual([""], frappe.get_route(), "Routed correctly"),

		// Click username on the navbar (Adminisrator) and verify visibility of all elements
		() => frappe.tests.click_navbar_item('navbar_user'),
		() => navbar_user_items.forEach(function(navbar_user_item) {
			assert.ok(frappe.tests.is_visible(navbar_user_item), "Visibility of "+navbar_user_item+" verified");
		}),

		// Click Help and verify visibility of all elements
		() => frappe.tests.click_navbar_item('Help'),
		() => modal_and_heading.forEach(function(modal) {
			assert.ok(frappe.tests.is_visible(modal), "Visibility of "+modal+" modal verified");
		}),

		// Goto Desk
		() => frappe.tests.click_navbar_item('Home'),
		() => frappe.timeout(1),

		// Click navbar-username and verify links of all menu items
		// Check if clicking on 'Set Desktop Icons' redirects you to the correct page
		() => frappe.tests.click_navbar_item('navbar_user'),
		() => frappe.tests.click_dropdown_item('Set Desktop Icons'),
		() => assert.deepEqual(["modules_setup"], frappe.get_route(), "Routed to 'modules_setup' by clicking on 'Set Desktop Icons'"),
		() => frappe.tests.click_navbar_item('Home'),

		// Check if clicking on 'My Settings' redirects you to the correct page
		() => frappe.tests.click_navbar_item('navbar_user'),
		() => frappe.tests.click_dropdown_item('My Settings'),
		() => assert.deepEqual(["Form", "User", "Administrator"], frappe.get_route(), "Routed to 'Form, User, Administrator' by clicking on 'My Settings'"),
		() => frappe.tests.click_navbar_item('Home'),

		// Check if clicking on 'Background Jobs' redirects you to the correct page
		() => frappe.tests.click_navbar_item('navbar_user'),
		() => frappe.tests.click_dropdown_item('Background Jobs'),
		() => assert.deepEqual(["background_jobs"], frappe.get_route(), "Routed to 'background_jobs' by clicking on 'Background Jobs'"),
		() => frappe.tests.click_navbar_item('Home'),

		// Click Help and check both modals
		// Check if clicking 'Documentation' opens the right modal
		() => frappe.tests.click_navbar_item('Help'),
		() => frappe.tests.click_dropdown_item('Documentation'),
		() => assert.ok(frappe.tests.is_visible('Documentation', 'span'), "Documentation modal popped"),
		() => frappe.tests.click_button('Close'),

		// Check if clicking 'About' opens the right modal
		() => frappe.tests.click_navbar_item('Help'),
		() => frappe.tests.click_dropdown_item('About'),
		() => assert.ok(frappe.tests.is_visible('Frappe Framework', 'div'), "Frappe Framework[About] modal popped"),
		() => frappe.tests.click_button('Close'),

		() => done()
	]);
});