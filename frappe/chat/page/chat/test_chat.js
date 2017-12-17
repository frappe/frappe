QUnit.test("test: Chat", function (assert)
{
	const done = assert.async(3);

	assert.expect(3);

	// test - frappe._.fuzzy_search
	frappe.run_serially([
		() => assert.equal(frappe._.fuzzy_search("foo", ["foobar", "tooti"]), "foobar"),
	]);

	// test - frappe.chat.profile.create
	frappe.run_serially([
		() => frappe.set_route('chat'),
		// empty promise
		() => frappe.chat.profile.create(),
		(profile) => {
			assert.equal(profile.status, "Online");
		},
		// one key only
		() => frappe.chat.profile.create("status"),
		(profile) => {
			assert.equal(Object.keys(profile).length, 1);
		},
		() => done()
	]);
});