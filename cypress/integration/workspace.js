context('Workspace 2.0', () => {
	before(() => {
		cy.visit('/login');
		cy.login();
		cy.visit('/app/website');
	});

	it('Navigate to page from sidebar', () => {
		cy.visit('/app/build');
		cy.get('.codex-editor__redactor .ce-block');
		cy.get('.sidebar-item-container[item-name="Settings"]').first().click();
		cy.location('pathname').should('eq', '/app/settings');
	});

	it('Create Private Page', () => {
		cy.get('.codex-editor__redactor .ce-block');
		cy.get('.custom-actions button[data-label="Create%20Workspace"]').click();
		cy.fill_field('title', 'Test Private Page', 'Data');
		cy.fill_field('icon', 'edit', 'Icon');
		cy.get_open_dialog().find('.modal-header').click();
		cy.get_open_dialog().find('.btn-primary').click();

		// check if sidebar item is added in pubic section
		cy.get('.sidebar-item-container[item-name="Test Private Page"]').should('have.attr', 'item-public', '0');

		cy.get('.standard-actions .btn-primary[data-label="Save Customizations"]').click();
		cy.wait(300);
		cy.get('.sidebar-item-container[item-name="Test Private Page"]').should('have.attr', 'item-public', '0');

		cy.wait(500);
		cy.get('.codex-editor__redactor .ce-block');
		cy.get('.standard-actions .btn-secondary[data-label=Edit]').click();
	});

	it('Add New Block', () => {
		cy.get('.codex-editor__redactor .ce-block');
		cy.get('.custom-actions .inner-group-button[data-label="Add%20Block"]').click();
		cy.get('.custom-actions .inner-group-button .dropdown-menu .block-menu-item-label').contains('Heading').click();
		cy.get(":focus").type('Header');
		cy.get(".ce-block:last").find('.ce-header').should('exist');

		cy.get('.custom-actions .inner-group-button[data-label="Add%20Block"]').click();
		cy.get('.custom-actions .inner-group-button .dropdown-menu .block-menu-item-label').contains('Text').click();
		cy.get(":focus").type('Paragraph text');
		cy.get(".ce-block:last").find('.ce-paragraph').should('exist');
	});

	it('Delete A Block', () => {
		cy.get(".ce-block:last").find('.delete-paragraph').click();
		cy.get(".ce-block:last").find('.ce-paragraph').should('not.exist');
	});

	it('Shrink and Expand A Block', () => {
		cy.get(".ce-block:last").find('.tune-btn').click();
		cy.get('.ce-settings--opened .ce-shrink-button').click();
		cy.get(".ce-block:last").should('have.class', 'col-11');
		cy.get('.ce-settings--opened .ce-shrink-button').click();
		cy.get(".ce-block:last").should('have.class', 'col-10');
		cy.get('.ce-settings--opened .ce-shrink-button').click();
		cy.get(".ce-block:last").should('have.class', 'col-9');
		cy.get('.ce-settings--opened .ce-expand-button').click();
		cy.get(".ce-block:last").should('have.class', 'col-10');
		cy.get('.ce-settings--opened .ce-expand-button').click();
		cy.get(".ce-block:last").should('have.class', 'col-11');
		cy.get('.ce-settings--opened .ce-expand-button').click();
		cy.get(".ce-block:last").should('have.class', 'col-12');
	});

	it('Change Header Text Size', () => {
		cy.get('.ce-settings--opened .cdx-settings-button[data-level="3"]').click();
		cy.get(".ce-block:last").find('.widget-head h3').should('exist');
		cy.get('.ce-settings--opened .cdx-settings-button[data-level="4"]').click();
		cy.get(".ce-block:last").find('.widget-head h4').should('exist');

		cy.get('.standard-actions .btn-primary[data-label="Save Customizations"]').click();
	});

	it('Delete Private Page', () => {
		cy.get('.codex-editor__redactor .ce-block');
		cy.get('.standard-actions .btn-secondary[data-label=Edit]').click();

		cy.get('.sidebar-item-container[item-name="Test Private Page"]').find('.sidebar-item-control .delete-page').click();
		cy.wait(300);
		cy.get('.modal-footer > .standard-actions > .btn-modal-primary:visible').first().click();
		cy.get('.standard-actions .btn-primary[data-label="Save Customizations"]').click();
		cy.get('.codex-editor__redactor .ce-block');
		cy.get('.sidebar-item-container[item-name="Test Private Page"]').should('not.exist');
	});

});