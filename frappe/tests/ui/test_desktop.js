QUnit.module('views');


QUnit.test("Verification of navbar menu links", function(assert) {
	assert.expect(14);
	let done = assert.async();

	frappe.run_serially([

		// Goto Home using button click to check if its working
		() => frappe.tests.clickText('Home'),
		() => assert.deepEqual([""], frappe.get_route()),


		// Click navbar-username and verify visibility of all elements 
		() => frappe.tests.click_navbar_user(),
		() => {
			assert.ok(frappe.tests.isVisible('Set Desktop Icons'));
			assert.ok(frappe.tests.isVisible('My Settings'));
			assert.ok(frappe.tests.isVisible('Reload'));
			assert.ok(frappe.tests.isVisible('View Website'));
			assert.ok(frappe.tests.isVisible('Background Jobs'));
			assert.ok(frappe.tests.isVisible('Logout'));
		},
		() => frappe.tests.click_navbar_help(),
		() => {
			assert.ok(frappe.tests.isVisible('Documentation'));
			assert.ok(frappe.tests.isVisible('About'));
		},
		() => frappe.tests.clickText('Home'),
		() => frappe.timeout(0.3),

		// Click navbar-username and verify links of all menu items
		() => frappe.tests.click_navbar_user(),
		() => frappe.tests.clickText('Set Desktop Icons'),
		() => assert.deepEqual(["modules_setup"], frappe.get_route()),
		() => frappe.tests.clickText('Home'),

		() => frappe.tests.click_navbar_user(),
		() => frappe.tests.clickText('My Settings'),
		() => assert.deepEqual(["Form", "User", "Administrator"], frappe.get_route()),
		() => frappe.tests.clickText('Home'),

		() => frappe.tests.click_navbar_user(),
		() => frappe.tests.clickText('Background Jobs'),
		() => assert.deepEqual(["background_jobs"], frappe.get_route()),
		() => frappe.tests.clickText('Home'),

		// Click Help and check both modals
		() => frappe.tests.click_navbar_help(),
		() => frappe.tests.clickText('Documentation'),
		() => assert.ok(frappe.tests.isVisible('Documentation', 'span')),
		() => frappe.tests.clickText('Close', 'button'),

		() => frappe.tests.click_navbar_help(),
		() => frappe.tests.clickText('About'),
		() => assert.ok(frappe.tests.isVisible('Frappe Framework', 'div')),
		() => frappe.tests.clickText('Close', 'button'),


		() => {return done();}


	]);
});