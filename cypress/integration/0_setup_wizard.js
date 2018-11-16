context('Setup Wizard', () => {
    before(() => {
        cy.login('Administrator', 'qwe')
        cy.visit('/desk#setup-wizard')
    })

    it('completes the setup wizard', () => {
        cy.get('.next-btn').click()
        cy.fill_field('country', 'India', 'Select')
        cy.get('.complete-btn').click()
        cy.wait(5000)
        cy.location('hash').should('eq', '')
    })
})
