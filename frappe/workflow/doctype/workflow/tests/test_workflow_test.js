QUnit.module('setup');

QUnit.test("Test Workflow", function(assert) {
	assert.expect(5);
	let done = assert.async();

	frappe.run_serially([
		() => frappe.set_route('Form', 'User', 'New User 1'),
		() => frappe.timeout(1),
		() => {
			cur_frm.set_value('email', 'test1@testmail.com');
			cur_frm.set_value('first_name', 'Test Name');
			cur_frm.set_value('send_welcome_email', 0);
			cur_frm.save();
		},
		() => frappe.timeout(2),
		() => frappe.tests.click_button('Actions'),
		() => frappe.timeout(0.5),
		() => {
			let review = $(`.dropdown-menu li:contains("Review"):visible`).size();
			let approve = $(`.dropdown-menu li:contains("Approve"):visible`).size();
			assert.equal(review, 1, "Review Action exists");
			assert.equal(approve, 1, "Approve Action exists");
		},
		() => frappe.tests.click_dropdown_item('Approve'),
		() => frappe.timeout(1),
		() => frappe.tests.click_button('Yes'),
		() => frappe.timeout(1),
		() => {
			assert.equal($('.msgprint').text(), "Did not saveInsufficient Permission for User", "Approve action working");
			frappe.tests.click_button('Close');
		},
		() => frappe.timeout(1),
		() => {
			$('.user-role input:eq(5)').click();
			cur_frm.save();
		},
		() => frappe.timeout(0.5),
		() => frappe.tests.click_button('Actions'),
		() => frappe.timeout(0.5),
		() => {
			let reject = $(`.dropdown-menu li:contains("Reject"):visible`).size();
			assert.equal(reject, 1, "Review Action exists");
		},
		() => frappe.tests.click_dropdown_item('Reject'),
		() => frappe.timeout(0.5),
		() =>	{
			if(frappe.tests.click_button('Close'))
				assert.equal(1, 1, "Reject action works");
		},
		() => done()
	]);
});