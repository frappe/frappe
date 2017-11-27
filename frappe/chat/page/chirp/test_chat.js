QUnit.test("test: Chirp", (assert) => {
	const done = assert.async()

	assert.expect(1)

	frappe.run_serially([
		() => frappe.set_route('chirp'),
		() => frappe.chat.profile.create(),
		(profile) => {
			assert.equal(profile.status, "Online")
		},
		() => done()
	])
})