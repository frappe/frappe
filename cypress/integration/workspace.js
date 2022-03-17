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

		cy.get('.standard-actions .btn-primary[data-label="Save"]').click();
		cy.wait(300);
		cy.get('.sidebar-item-container[item-name="Test Private Page"]').should('have.attr', 'item-public', '0');

		cy.wait(500);
		cy.get('.codex-editor__redactor .ce-block');
		cy.get('.standard-actions .btn-secondary[data-label=Edit]').click();
	});

	it('Add New Block', () => {
		cy.get('.ce-block').click().type('{enter}');
		cy.get('.block-list-container .block-list-item').contains('Heading').click();
		cy.get(":focus").type('Header');
		cy.get(".ce-block:last").find('.ce-header').should('exist');

		cy.get('.ce-block:last').click().type('{enter}');
		cy.get('.block-list-container .block-list-item').contains('Text').click();
		cy.get(":focus").type('Paragraph text');
		cy.get(".ce-block:last").find('.ce-paragraph').should('exist');
	});

	it('Delete A Block', () => {
		cy.get(":focus").click();
		cy.get('.paragraph-control .setting-btn').click();
		cy.get('.paragraph-control .dropdown-item').contains('Delete').click();
		cy.get(".ce-block:last").find('.ce-paragraph').should('not.exist');
	});

	it('Shrink and Expand A Block', () => {
		cy.get(":focus").click();
		cy.get('.ce-block:last .setting-btn').click();
		cy.get('.ce-block:last .dropdown-item').contains('Shrink').click();
		cy.get(".ce-block:last").should('have.class', 'col-xs-11');
		cy.get('.ce-block:last .dropdown-item').contains('Shrink').click();
		cy.get(".ce-block:last").should('have.class', 'col-xs-10');
		cy.get('.ce-block:last .dropdown-item').contains('Shrink').click();
		cy.get(".ce-block:last").should('have.class', 'col-xs-9');
		cy.get('.ce-block:last .dropdown-item').contains('Expand').click();
		cy.get(".ce-block:last").should('have.class', 'col-xs-10');
		cy.get('.ce-block:last .dropdown-item').contains('Expand').click();
		cy.get(".ce-block:last").should('have.class', 'col-xs-11');
		cy.get('.ce-block:last .dropdown-item').contains('Expand').click();
		cy.get(".ce-block:last").should('have.class', 'col-xs-12');

		cy.get('.standard-actions .btn-primary[data-label="Save"]').click();
	});

	it('Delete Private Page', () => {
		cy.get('.codex-editor__redactor .ce-block');
		cy.get('.standard-actions .btn-secondary[data-label=Edit]').click();

		cy.get('.sidebar-item-container[item-name="Test Private Page"]')
			.find('.sidebar-item-control .setting-btn').click();
		cy.get('.sidebar-item-container[item-name="Test Private Page"]')
			.find('.dropdown-item[title="Delete Workspace"]').click({force: true});
		cy.wait(300);
		cy.get('.modal-footer > .standard-actions > .btn-modal-primary:visible').first().click();
		cy.get('.standard-actions .btn-primary[data-label="Save"]').click();
		cy.get('.codex-editor__redactor .ce-block');
		cy.get('.sidebar-item-container[item-name="Test Private Page"]').should('not.exist');
	});

});