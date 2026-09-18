describe("Dashboard Chart Legend", { scrollBehavior: false }, () => {
	const chart_name = "TEST-LEGEND-TRUNCATION";
	const dashboard_name = "TEST-LEGEND-DASHBOARD";
	const marker = "legend truncation test";

	// DocType names longer than the 18 character legend cap
	const long_labels = [
		"Dashboard Chart Source",
		"Document Naming Rule",
		"Workspace Sidebar Item",
	];

	before(() => {
		cy.login();
		cy.visit("/desk");

		long_labels.forEach((reference_type) => {
			cy.insert_doc(
				"ToDo",
				{
					description: `${marker} ${reference_type}`,
					reference_type: reference_type,
				},
				true
			);
		});

		cy.insert_doc(
			"Dashboard Chart",
			{
				is_standard: 0,
				chart_name: chart_name,
				chart_type: "Group By",
				document_type: "ToDo",
				group_by_based_on: "reference_type",
				group_by_type: "Count",
				type: "Percentage",
				timeseries: 0,
				filters_json: JSON.stringify([["ToDo", "description", "like", `%${marker}%`]]),
			},
			true
		);

		cy.insert_doc(
			"Dashboard",
			{
				name: dashboard_name,
				dashboard_name: dashboard_name,
				is_standard: 0,
				charts: [{ chart: chart_name }],
			},
			true
		);
	});

	it("keeps long legend labels truncated when a circular chart is re-rendered", () => {
		cy.visit(`/desk/dashboard-view/${dashboard_name}`);

		cy.get(".chart-legend .legend-dataset-label").first().should("contain", "...");

		cy.get(".chart-legend").invoke("attr", "data-first-render", "1");

		// the path every chart filter and timespan handler goes through
		cy.window().then((win) => {
			const widget = win.frappe.dashboard.chart_group.widgets_list.find(
				(w) => w.chart_doc && w.chart_doc.chart_name === chart_name
			);
			expect(widget, "chart widget was found on the page").to.exist;
			expect(widget.dashboard_chart, "chart was already rendered once").to.exist;
			widget.fetch_and_update_chart();
		});

		cy.get(".chart-legend:not([data-first-render])")
			.find(".legend-dataset-label")
			.first()
			.should("contain", "...");
	});
});
