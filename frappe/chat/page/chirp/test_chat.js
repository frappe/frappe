QUnit.test("test: Chirp", (assert) => {
	const done = assert.async(2)

	assert.expect(2)

	// test - frappe.chat.profile.create
	frappe.run_serially([
		() => frappe.set_route('chirp'),
		// empty promise
		() => frappe.chat.profile.create(),
		(profile) => {
			assert.equal(profile.status, "Online")
		},
		// one key only
		() => frappe.chat.profile.create("status"),
		(profile) => {
			assert.equal(Object.keys(profile).length, 1)
		},
		() => done()
	])
})