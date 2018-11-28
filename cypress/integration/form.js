context('Form', () => {
    before(() => {
        cy.login('Administrator', 'qwe')
        cy.visit('/desk')
    })

    it('create a new form', () => {
        cy.visit('/desk#Form/ToDo/New ToDo 1')
        cy.get('[data-fieldname="description"] .ql-editor').type('this is a test todo', { delay: 50 })
        cy.scrollTo(0, 0)
        cy.get('.primary-action').click()
        cy.visit('/desk#List/ToDo')
        cy.location('hash').should('eq', '#List/ToDo/List')
        cy.get('.list-row').should('contain', 'this is a test todo')
    })
})
