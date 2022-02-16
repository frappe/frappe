import custom_submittable_doctype from '../fixtures/custom_submittable_doctype';
const doctype_name = custom_submittable_doctype.name;

context('Report View', () => {
	before(() => {
		cy.login();
		cy.visit('/app/website');
		cy.insert_doc('DocType', custom_submittable_doctype, true);
		cy.clear_cache();
		cy.insert_doc(doctype_name, {
			'title': 'Doc 1',
			'description': 'Random Text',
			'enabled': 0,
			'docstatus': 1 // submit document
		}, true);
		return cy.window().its('frappe').then(frappe => {
			return frappe.call("frappe.tests.ui_test_helpers.create_multiple_contact_records");
		});
	});

	it('Field with enabled allow_on_submit should be editable.', () => {
		cy.intercept('POST', 'api/method/frappe.client.set_value').as('value-update');
		cy.visit(`/app/List/${doctype_name}/Report`);

		// check status column added from docstatus
		cy.get('.dt-row-0 > .dt-cell--col-3').should('contain', 'Submitted');
		let cell = cy.get('.dt-row-0 > .dt-cell--col-4');

		// select the cell
		cell.dblclick();
		cell.get('.dt-cell__edit--col-4').findByRole('checkbox').check({ force: true });
		cy.get('.dt-row-0 > .dt-cell--col-5').click();
		cy.wait('@value-update');

		cy.call('frappe.client.get_value', {
			doctype: doctype_name,
			filters: {
				title: 'Doc 1',
			},
			fieldname: 'enabled'
		}).then(r => {
			expect(r.message.enabled).to.equals(1);
		});
	});

	it('test load more with count selection buttons', () => {
		cy.visit('/app/contact/view/report');

		cy.get('.list-paging-area .list-count').should('contain.text', '20 of');
		cy.get('.list-paging-area .btn-more').click();
		cy.get('.list-paging-area .list-count').should('contain.text', '40 of');
		cy.get('.list-paging-area .btn-more').click();
		cy.get('.list-paging-area .list-count').should('contain.text', '60 of');

		cy.get('.list-paging-area .btn-group .btn-paging[data-value="100"]').click();

		cy.get('.list-paging-area .list-count').should('contain.text', '100 of');
		cy.get('.list-paging-area .btn-more').click();
		cy.get('.list-paging-area .list-count').should('contain.text', '200 of');
		cy.get('.list-paging-area .btn-more').click();
		cy.get('.list-paging-area .list-count').should('contain.text', '300 of');

		// check if refresh works after load more
		cy.get('.page-head .standard-actions [data-original-title="Refresh"]').click();
		cy.get('.list-paging-area .list-count').should('contain.text', '300 of');

		cy.get('.list-paging-area .btn-group .btn-paging[data-value="500"]').click();

		cy.get('.list-paging-area .list-count').should('contain.text', '500 of');
		cy.get('.list-paging-area .btn-more').click();
		cy.get('.list-paging-area .list-count').should('contain.text', '1000 of');
	});
});
