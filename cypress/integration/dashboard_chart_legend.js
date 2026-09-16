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

	// a label may not run into the swatch of the next item on its row
	const expect_no_legend_overlap = (selector) => {
		cy.get(selector).then(($legend) => {
			const items = $legend.children().toArray();

			items.forEach((item, index) => {
				const label = item.querySelector(".legend-dataset-label");
				const next = items[index + 1];
				if (!label || !next) return;

				const swatch = next.querySelector("rect");
				if (!swatch) return;

				const label_box = label.getBoundingClientRect();
				const swatch_box = swatch.getBoundingClientRect();
				if (Math.abs(swatch_box.top - label_box.top) > 20) return;

				expect(
					label_box.right,
					`legend label "${label.textContent}" runs into the next swatch`
				).to.be.at.most(swatch_box.left);
			});
		});
	};

	it("keeps long legend labels truncated and clear of the next swatch across re-renders", () => {
		cy.visit("/desk");

		// collect widgets as they render; set_route keeps this window alive
		cy.window().then((win) => {
			const ChartWidget = win.frappe.widget.widget_factory.chart;
			const render = ChartWidget.prototype.render;
			win.test_chart_widgets = [];
			ChartWidget.prototype.render = function (...args) {
				if (!win.test_chart_widgets.includes(this)) {
					win.test_chart_widgets.push(this);
				}
				return render.apply(this, args);
			};
		});

		cy.window().then((win) => win.frappe.set_route("dashboard-view", dashboard_name));

		cy.get(".chart-legend .legend-dataset-label").first().should("contain", "...");
		expect_no_legend_overlap(".chart-legend");

		cy.get(".chart-legend").invoke("attr", "data-first-render", "1");

		// the path every chart filter and timespan handler goes through
		cy.window().then((win) => {
			const widget = win.test_chart_widgets.find(
				(w) => w.chart_doc && w.chart_doc.chart_name === chart_name
			);
			expect(widget, "chart widget was captured").to.exist;
			expect(widget.dashboard_chart, "chart was already rendered once").to.exist;
			widget.fetch_and_update_chart();
		});

		cy.get(".chart-legend:not([data-first-render])")
			.find(".legend-dataset-label")
			.first()
			.should("contain", "...");
		expect_no_legend_overlap(".chart-legend:not([data-first-render])");
	});
});
