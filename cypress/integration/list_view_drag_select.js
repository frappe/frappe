context("List View", () => {
	before(() => {
		cy.login();
		cy.go_to_list("DocType");
	});

	it("List view check rows on drag", () => {
		cy.get(".filter-x-button").click();
		cy.get(".list-row-checkbox").then(($checkbox) => {
			cy.wrap($checkbox).first().trigger("mousedown");
			cy.get(".level.list-row").each(($ele) => {
				cy.wrap($ele).trigger("mousemove");
			});
			cy.document().trigger("mouseup");
		});

		cy.get(".level.list-row .list-row-checkbox").each(($checkbox) => {
			cy.wrap($checkbox).should("be.checked");
		});
	});

	it("Check all rows are checked", () => {
		cy.get(".level.list-row .list-row-checkbox")
			.its("length")
			.then((len) => {
				cy.get(".level-item.list-header-meta")
					.should("be.visible")
					.should("contain.text", `${len} items selected`);
			});
	});

	it("List view uncheck rows on drag", () => {
		cy.get(".list-row-checkbox").then(($checkbox) => {
			cy.wrap($checkbox).first().trigger("mousedown");
			cy.get(".level.list-row").each(($ele) => {
				cy.wrap($ele).trigger("mousemove");
			});
			cy.document().trigger("mouseup");
		});

		cy.get(".level.list-row .list-row-checkbox").each(($checkbox) => {
			cy.wrap($checkbox).should("not.be.checked");
		});
	});

	it("Check all rows are unchecked", () => {
		cy.get(".level-item.list-header-meta").should("not.be.visible");
	});
});
