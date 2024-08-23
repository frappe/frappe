describe("Dashboard view", { scrollBehavior: false }, () => {
	before(() => {
		cy.login();
		cy.visit("/app");
	});

	it("should load", () => {
		const chart = "TODO-YEARLY-TRENDS";
		const dashboard = "TODO-TEST-DASHBOARD"; // check slash in name intentionally.

		cy.insert_doc(
			"Dashboard Chart",
			{
				is_standard: 0,
				chart_name: chart,
				chart_type: "Count",
				document_type: "ToDo",
				parent_document_type: "",
				based_on: "creation",
				group_by_type: "Count",
				timespan: "Last Year",
				time_interval: "Yearly",
				timeseries: 1,
				type: "Line",
				filters_json: "[]",
			},
			true
		);

		cy.insert_doc(
			"Dashboard",
			{
				name: dashboard,
				dashboard_name: dashboard,
				is_standard: 0,
				charts: [
					{
						chart: chart,
					},
				],
			},
			true
		);

		cy.visit(`/app/dashboard-view/${dashboard}`);

		// expect chart to be loaded
		cy.findByText(chart).should("be.visible");
	});
});
