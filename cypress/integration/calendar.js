context('Login', () => {
	beforeEach(() => {
		cy.login('Administrator', 'qwe');
		cy.visit('/desk');
	});

	it('navigates to calendar', () => {
		cy.get('#navbar-search')
			.type('calendar{downarrow}{enter}', { delay: 100 });
		cy.location('hash').should('eq', '#calendar');
	});

	it("Click to Event and edit", () => {
		cy.visit('/desk#calendar');
		cy.get('.fc-day-grid-event')
			.click();
		cy.get(".btn.btn-default.btn-xs:contains('Edit')").click();
		cy.location("hash").should("eq", "#Form/Event/EV00001");
	});

	it("Visit from Doctype", () =>{
		cy.visit("/desk#List/Event/List");
		cy.get("a.cal").click({ force: true });
		cy.location("hash").should("eq", '#calendar/Event');
	});

	it("drag n create event", () =>{
		cy.visit("/desk#calendar");
		cy.get(".fc-day[data-date='2018-12-13']")
			.trigger('mousedown', {pageX: 691, pageY: 421, which: 1, force: true});
		cy.get(".fc-day[data-date='2018-12-14']")
			.trigger("mousemove", {pageX: 802, pageY: 421, which: 1, force: true});
		cy.get(".fc-day[data-date='2018-12-14']")
			.trigger("mouseup", {pageX: 802, pageY: 421, which: 1, force: true});
		cy.location("hash").should("eq", "#Form/Event/New%20Event%201");
	});

	it("drag the event", () =>{
		cy.visit('/desk#calendar');
		cy.get('.fc-day-grid-event')
			.trigger('mousedown', {pageX: 349, pageY: 341, which: 1, force: true});
		cy.get(".fc-day[data-date='2018-12-14']")
			.trigger("mousemove", {pageX: 459, pageY: 459, which: 1, force: true});
		cy.get(".fc-day[data-date='2018-12-14']")
			.trigger("mouseup", {pageX: 459, pageY: 459, which: 1, force: true});

	});

	it("Visit from tools", () =>{
		cy.visit('desk#modules/Desk');
		cy.get("a:contains('Calendar')").click({ force: true });
		cy.location("hash").should("eq", '#calendar');
	})
});