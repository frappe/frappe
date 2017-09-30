QUnit.module('Core');

QUnit.test("test: Role Profile", function (assert) {
	let done = assert.async();

	assert.expect(3);

	frappe.run_serially([
		// insert a new User
		() => frappe.tests.make('Role Profile', [
			{role_name: 'Test 1'}
		]),

		() => {
			$('input.box')[0].checked = true;
			$('input.box')[2].checked = true;
			$('input.box')[4].checked = true;
			cur_frm.save();
		},

		() => frappe.timeout(1),
		() => cur_frm.refresh(),
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
