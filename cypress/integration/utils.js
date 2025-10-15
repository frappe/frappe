context("Utils", () => {
	before(() => {
		cy.login();
		cy.visit("/app");
	});

	function run_util(name, ...args) {
		return cy
			.window()
			.its("frappe")
			.then((frappe) => {
				return frappe.utils[name](...args);
			});
	}

	it("should round hidden seconds to minutes", () => {
		run_util("seconds_to_duration", 89, { hide_seconds: 1 }).then((duration) => {
			expect(duration).to.deep.equal({
				days: 0,
				hours: 0,
				minutes: 1,
				seconds: 0,
			});
		});

		run_util("seconds_to_duration", -89, { hide_seconds: 1 }).then((duration) => {
			expect(duration).to.deep.equal({
				days: -0,
				hours: -0,
				minutes: -1,
				seconds: 0,
			});
		});

		run_util("seconds_to_duration", 91, { hide_seconds: 1 }).then((duration) => {
			expect(duration).to.deep.equal({
				days: 0,
				hours: 0,
				minutes: 2,
				seconds: 0,
			});
		});

		run_util("seconds_to_duration", -91, { hide_seconds: 1 }).then((duration) => {
			expect(duration).to.deep.equal({
				days: -0,
				hours: -0,
				minutes: -2,
				seconds: 0,
			});
		});

		run_util("seconds_to_duration", 60 * 60, { hide_seconds: 1 }).then((duration) => {
			expect(duration).to.deep.equal({
				days: 0,
				hours: 1,
				minutes: 0,
				seconds: 0,
			});
		});

		run_util("seconds_to_duration", 15 * 60, { hide_seconds: 1 }).then((duration) => {
			expect(duration).to.deep.equal({
				days: 0,
				hours: 0,
				minutes: 15,
				seconds: 0,
			});
		});
	});

	it("should parse days, hours, minutes and seconds", () => {
		run_util("seconds_to_duration", 60 * 60 * 24 + 60 * 60 + 60 + 1).then((duration) => {
			expect(duration).to.deep.equal({
				days: 1,
				hours: 1,
				minutes: 1,
				seconds: 1,
			});
		});

		run_util("seconds_to_duration", (60 * 60 * 24 + 60 * 60 + 60 + 1) * -1).then(
			(duration) => {
				expect(duration).to.deep.equal({
					days: -1,
					hours: -1,
					minutes: -1,
					seconds: -1,
				});
			}
		);

		run_util("seconds_to_duration", 60 * 60 * 24 + 60 * 60 + 60 + 1, {
			hide_days: 1,
			hide_seconds: 1,
		}).then((duration) => {
			expect(duration).to.deep.equal({
				days: 0,
				hours: 25,
				minutes: 1,
				seconds: 0,
			});
		});

		run_util("seconds_to_duration", (60 * 60 * 24 + 60 * 60 + 60 + 1) * -1, {
			hide_days: 1,
			hide_seconds: 1,
		}).then((duration) => {
			expect(duration).to.deep.equal({
				days: 0,
				hours: -25,
				minutes: -1,
				seconds: 0,
			});
		});
	});
});
