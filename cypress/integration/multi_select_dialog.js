context('MultiSelectDialog', () => {
	before(() => {
		cy.login();
		cy.visit('/app');
	});

	function open_multi_select_dialog() {
		cy.window().its('frappe').then(frappe => {
			new frappe.ui.form.MultiSelectDialog({
				doctype: "Assignment Rule",
				target: {},
				setters: {
					document_type: null,
					priority: null
				},
				add_filters_group: 1,
				allow_child_item_selection: 1,
				child_fieldname: "assignment_days",
				child_columns: ["day"]
			});
		});
	}

	it('multi select dialog api works', () => {
		open_multi_select_dialog();
		cy.get_open_dialog().should('contain', 'Select Assignment Rules');
	});

	it('checks for filters', () => {
		['search_term', 'document_type', 'priority'].forEach(fieldname => {
			cy.get_open_dialog().get(`.frappe-control[data-fieldname="${fieldname}"]`).should('exist');
		});

		// add_filters_group: 1 should add a filter group
		cy.get_open_dialog().get(`.frappe-control[data-fieldname="filter_area"]`).should('exist');

	});

	it('checks for child item selection', () => {
		cy.get_open_dialog()
			.get(`.dt-row-header`).should('not.exist');

		cy.get_open_dialog()
			.get(`.frappe-control[data-fieldname="allow_child_item_selection"]`)
			.should('exist')
			.click();

		cy.get_open_dialog()
			.get(`.frappe-control[data-fieldname="child_selection_area"]`)
			.should('exist');

		cy.get_open_dialog()
			.get(`.dt-row-header`).should('contain', 'Assignment Rule');

		cy.get_open_dialog()
			.get(`.dt-row-header`).should('contain', 'Day');
	});
});