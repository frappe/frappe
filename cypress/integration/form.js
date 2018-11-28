context('Form', () => {
    before(() => {
        cy.login('Administrator', 'qwe')
        cy.visit('/desk')
    })

    it('create a new form', () => {
        cy.visit('/desk#Form/ToDo/New ToDo 1')
        cy.wait(2000)
        cy.get('[data-fieldname="description"] .ql-editor').type('this is a test todo')
        cy.scrollTo(0, 0)
        cy.wait(2000)
        cy.get('.primary-action').click()
        cy.visit('/desk#List/ToDo')
        cy.location('hash').should('eq', '#List/ToDo/List')
        cy.get('.list-row').should('contain', 'this is a test todo')
    })
})
