context("Utils", () => {
	before(() => {
		cy.login();
		cy.visit("/desk");
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

	it("should escape the docname when it is used as the link text", () => {
		run_util("get_form_link", "ToDo", "<img src=x onerror=alert(1)>", true).then((link) => {
			expect(link).to.equal(
				'<a href="/desk/todo/%3Cimg%20src%3Dx%20onerror%3Dalert(1)%3E">' +
					"&lt;img src&#x3D;x onerror&#x3D;alert(1)&gt;</a>"
			);
		});
	});

	it("should not escape display text passed by the caller", () => {
		run_util("get_form_link", "ToDo", "TODO-0001", true, "<b>Open item</b>").then((link) => {
			expect(link).to.equal('<a href="/desk/todo/TODO-0001"><b>Open item</b></a>');
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
