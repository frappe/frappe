context('Awesome Bar', () => {
    before(() => {
        cy.login('Administrator', 'qwe')
        cy.visit('/desk')
    })

    beforeEach(() => {
        cy.get('.navbar-home').click()
    })

    it('create a new form', () => {
        cy.visit('/desk#Form/ToDo/New ToDo 1')
        cy.fill_field('description', 'this is a test todo', 'Text Editor')
        cy.get('.primary-action').click()
        cy.visit('/desk#List/ToDo')
        cy.location('hash').should('eq', '#List/ToDo/List')
        cy.get('.list-row').should('contain', 'this is a test todo')
    })
})
