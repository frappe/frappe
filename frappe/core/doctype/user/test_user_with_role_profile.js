QUnit.module('Core');

QUnit.test("test: Set role profile in user", function (assert) {
	let done = assert.async();

	assert.expect(3);

	frappe.run_serially([
		// insert a new User
		() => frappe.tests.make('User', [
			{email: 'test@test1.com'},
			{first_name: 'Test'},
			{send_welcome_email: 0}
		]),

		() => frappe.timeout(2),
		() => {
			return frappe.tests.set_form_values(cur_frm, [
				{role_name:'Test 1'}
			]);
		},

		() => cur_frm.save(),
		() => frappe.timeout(2),

		() => {
			// assert.equal(cur_frm.doc.roles[0].role, 'value');
			assert.equal($('input.box')[0].checked, true);
			assert.equal($('input.box')[2].checked, true);
			assert.equal($('input.box')[4].checked, true);
		},
		() => done()
	]);

});
