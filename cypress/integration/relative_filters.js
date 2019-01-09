context('Relative Timeframe', () => {
	beforeEach(() => {
		cy.login('Administrator', 'qwe');
		cy.visit('/desk');
	});
  it('set relative filter and check list', () =>{
		cy.visit('/desk#List/Sales%20Order/List');
    cy.get('btn.btn-default.btn-xs.add-filter.text-muted:contains("Add Filter")').click()
    cy.get('input.form-control').type("Delivery Date").blur()
    cy.get('select.condition.form-control').select("Next")
    cy.get('select.input-with-feedback.form-control').select("1 month")
    cy.get('set-filter-and-run.btn.btn-sm.btn-primary.pull-left').click()
  });
}
