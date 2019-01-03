context('Calendar', () => {
	beforeEach(() => {
		cy.login('Administrator', 'qwe');
		cy.visit('/desk');
	});

	it('navigates to calendar from awesomebar', () => {
		cy.get('#navbar-search')
			.type('calendar{downarrow}{enter}', { delay: 100 });
		cy.location('hash').should('eq', '#calendar');
	});

	it('drag n create event', () =>{
		cy.visit('/desk#calendar');

		cy.get('.fc-bg:first > table > tbody > tr')
			.trigger('mousedown', {pageX: 691, pageY: 421, which: 1, force: true});
		cy.get('.fc-bg:first > table > tbody > tr')
			.trigger('mousemove', {pageX: 802, pageY: 421, which: 1, force: true});
		cy.get('.fc-bg:first > table > tbody > tr')
			.trigger('mouseup', {pageX: 802, pageY: 421, which: 1, force: true});

		cy.fill_field('subject', 'JSFoo')
		cy.fill_field('event_type', 'Public', 'Select')
		cy.fill_field('description', 'This is JavaScript Event at Pune', 'Text Editor')
		// cy.get('input[data-fieldname="subject"]')
		// 	.type('JSFoo');
		// cy.get('select[data-fieldname="event_type"]')
		// 	.select('Public');
		// cy.get('')
		// 	.type("This is Jsfoo event");
		cy.get(".btn.btn-primary.btn-sm.primary-action:not(.hide)").click();

		cy.location('hash').should('eq', '#Form/Event/EV00001');
	});

	it('click to event and edit', () => {
		cy.visit('/desk#calendar');
		cy.get('.fc-day-grid-event')
			.click();
		cy.get('.btn.btn-default.btn-xs:contains("Edit")').click();
		cy.location('hash').should('eq', '#Form/Event/EV00001');
	});

	it('visit from list', () => {
		cy.visit('/desk#List/Event/List');
		cy.get('a.cal').click({ force: true });
		cy.location('hash').should('eq', '#calendar/Event');
	});

	it('drag the event', () =>{
		cy.visit('/desk#calendar');
		var today
		cy.window().its('frappe').then(frappe => {
			today = frappe.datetime.get_today();
		})
		cy.get('.fc-day-grid-event')
			.trigger('mousedown', {pageX: 349, pageY: 341, which: 1, force: true});
		cy.get('.layout-main-section')
			.trigger('mousemove', {pageX: 459, pageY: 459, which: 1, force: true});
		cy.get('.layout-main-section')
			.trigger('mouseup', {pageX: 459, pageY: 459, which: 1, force: true});

	});

	it('Visit from tools', () =>{
		cy.visit('desk#modules/Desk');
		cy.get('a:contains("Calendar")').click({ force: true });
		cy.location('hash').should('eq', '#calendar');
	});
});