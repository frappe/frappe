// Fails when a cold desk v2 load or a save sends more API calls than its baseline.
const BUDGETS = "frontend/speed-budgets.json";
const QUIET_MS = 1500;
const MAX_WAITS = 20;

context("Desk v2 API calls", () => {
	let budgets;
	let todo;

	before(() => {
		cy.login();
		cy.readFile(BUDGETS).then((file) => (budgets = file));
		cy.visit("/desk");
		cy.call("frappe.tests.ui_test_helpers.create_todo", {
			description: "Count the desk v2 API calls",
		}).then((r) => (todo = r.message.name));
	});

	it("loads home cold", () => {
		coldVisit("/apps/desk").then((calls) => expectBaseline("home", calls));
	});

	it("loads the list cold", () => {
		coldVisit("/apps/desk/todo").then((calls) => expectBaseline("list", calls));
	});

	it("loads a record cold", () => {
		coldVisit(`/apps/desk/todo/${todo}`).then((calls) => expectBaseline("record", calls));
	});

	it("saves a record", () => {
		coldVisit(`/apps/desk/todo/${todo}`);
		cy.get('[data-fieldname="description"]').click();
		cy.focused().type(" again");
		countCalls(() => cy.findByRole("button", { name: "Save" }).click()).then((calls) =>
			expectBaseline("save", calls)
		);
		cy.request(`/api/v2/document/ToDo/${todo}`)
			.its("body.data.description")
			.should("contain", " again");
	});

	function expectBaseline(name, calls) {
		const baseline = budgets[name].baseline.calls;
		const message =
			`${name} sent ${calls.length} API calls, baseline ${baseline}. ` +
			`Remove the calls, or raise the baseline in ${BUDGETS} to ${calls.length}.\n` +
			calls.join("\n");
		expect(calls.length, message).to.be.at.most(baseline);
	}
});

function coldVisit(path) {
	cy.clearAllLocalStorage();
	cy.clearAllSessionStorage();
	cy.wrap(
		Cypress.automation("remote:debugger:protocol", { command: "Network.clearBrowserCache" })
	);
	return countCalls(() => cy.visit(path));
}

function countCalls(action) {
	const calls = [];
	let pending = 0;
	cy.intercept({ url: "/api/**" }, (req) => {
		calls.push(`${req.method} ${req.url.replace(Cypress.config("baseUrl"), "")}`);
		pending++;
		req.on("after:response", () => pending--);
	});
	action();
	waitForQuiet(calls, () => pending);
	return cy.wrap(calls, { log: false });
}

function waitForQuiet(calls, pending, seen = -1, waits = 0) {
	cy.wait(QUIET_MS, { log: false }).then(() => {
		if (!pending() && calls.length === seen) return;
		if (waits === MAX_WAITS) {
			throw new Error(
				`API calls did not stop after ${MAX_WAITS} waits:\n${calls.join("\n")}`
			);
		}
		waitForQuiet(calls, pending, calls.length, waits + 1);
	});
}
