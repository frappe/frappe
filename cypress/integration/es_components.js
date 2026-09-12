// Espresso component tests, driven through the Component Explorer page
// (/desk/component-explorer). The explorer already mounts every component
// with real desk CSS, so it doubles as the test fixture.
//
// This is the EXEMPLAR spec — Dropdown behavior plus the toast HTML-message
// sanitisation regression. Once the pattern is confirmed on CI, the other
// components follow the same shape.
//
// Conventions worth copying:
//  - switch components with the deterministic render hook, not the picker
//    widget: frappe.pages["component-explorer"].render_component(name)
//  - scope to a group by its visible heading (cy.contains(".explorer-group",
//    title)) so reordering examples doesn't break selectors
//  - keyboard events go through .trigger("keydown", { key }) — cy.type()
//    only works on inputs/textareas, not <button> triggers

context("Espresso components", () => {
	before(() => {
		cy.login();
	});

	beforeEach(() => {
		cy.visit("/desk/component-explorer");
		// the page renders "Button" by default; wait for that first paint
		cy.get(".explorer-groups[data-component]").should("exist");
	});

	// Render a specific component and wait until it's on screen.
	function show(component) {
		cy.window().then((win) => {
			win.frappe.pages["component-explorer"].render_component(component);
		});
		return cy.get(`.explorer-groups[data-component="${component}"]`).should("exist");
	}

	describe("Dropdown", () => {
		beforeEach(() => show("Dropdown"));

		it("toggles open and closed on trigger click", () => {
			cy.contains(".explorer-group", "Basic actions")
				.find('[aria-haspopup="menu"]')
				.first()
				.as("trigger");

			cy.get("@trigger").click();
			cy.get(".es-menu[data-state='open']").should("exist");

			// the trigger owns its own click (it's in the menu's ignore list),
			// so clicking it again closes rather than reopening
			cy.get("@trigger").click();
			cy.get(".es-menu[data-state='open']").should("not.exist");
		});

		it("opens on ArrowDown onto the first row, and Escape closes + returns focus to the trigger", () => {
			cy.contains(".explorer-group", "Basic actions")
				.find('[aria-haspopup="menu"]')
				.first()
				.as("trigger");

			// keyboard open moves focus into the menu (mouse open would not)
			cy.get("@trigger").trigger("keydown", { key: "ArrowDown" });
			cy.get(".es-menu[data-state='open']").should("exist");
			cy.get(".es-menu__item[data-highlighted]").should("have.length", 1);

			// keyboard-open focuses the first row; Escape on it closes the menu
			cy.get(".es-menu__item[data-highlighted]").trigger("keydown", { key: "Escape" });
			cy.get(".es-menu[data-state='open']").should("not.exist");
			cy.get("@trigger").should("have.focus");
		});

		it("closes on Escape after a mouse open — the panel holds focus, so the cursor's position doesn't matter", () => {
			cy.contains(".explorer-group", "Basic actions")
				.find('[aria-haspopup="menu"]')
				.first()
				.as("trigger");

			// a plain click is a mouse open (no keyboard); the menu still
			// focuses its own panel, so Escape closes it
			cy.get("@trigger").click();
			cy.get(".es-menu[data-state='open']").should("exist").and("have.focus");

			cy.focused().trigger("keydown", { key: "Escape" });
			cy.get(".es-menu[data-state='open']").should("not.exist");
			cy.get("@trigger").should("have.focus");
		});

		it("renders a disabled option as a real disabled button, never a live row", () => {
			cy.contains(".explorer-group", "Groups, shortcuts and disabled rows")
				.find('[aria-haspopup="menu"]')
				.first()
				.click();

			cy.get(".es-menu[data-state='open']").should("exist");
			// the "Archive" item is disabled — must be an inert <button disabled>,
			// never a live row. cy.contains(selector, text) returns the matching
			// .es-menu__item itself, not the inner label span.
			cy.contains(".es-menu__item", "Archive").should("match", "button").and("be.disabled");
		});

		it("async options open in a loading state, then fill in when the promise settles", () => {
			cy.contains(".explorer-group", "Async items")
				.find('[aria-haspopup="menu"]')
				.first()
				.click();

			// the panel opens immediately with the placeholder (aria-busy),
			// no rows yet
			cy.get(".es-menu[data-state='open']")
				.should("have.attr", "aria-busy", "true")
				.find(".es-menu__loading")
				.should("exist");
			cy.get(".es-menu__item").should("not.exist");

			// the demo resolves after 600ms — the rows replace the placeholder
			// and the busy state clears
			cy.contains(".es-menu__item", "Fetched row 1").should("exist");
			cy.get(".es-menu[data-state='open']").should("not.have.attr", "aria-busy");
			cy.get(".es-menu__loading").should("not.exist");

			// the swapped-in rows are live
			cy.contains(".es-menu__item", "Fetched row 2").click();
			cy.get(".es-menu[data-state='open']").should("not.exist");
			cy.contains(".es-toast", "Row 2").should("exist");
		});

		it("a function submenu loads on hover and swaps in its rows", () => {
			cy.contains(".explorer-group", "Async items")
				.find('[aria-haspopup="menu"]')
				.eq(1)
				.click();

			// hover intent starts the fetch and opens the panel after the delay
			cy.contains(".es-menu__item", "Recent documents").trigger("pointerenter");
			cy.get(".es-menu[data-state='open']").should("have.length", 2);

			// resolved rows land in the submenu panel and activate normally
			cy.contains(".es-menu__item", "Doc A").should("exist");
			cy.contains(".es-menu__item", "Doc A").click();
			cy.get(".es-menu[data-state='open']").should("not.exist");
			cy.contains(".es-toast", "Doc A").should("exist");
		});

		it("a rejected submenu shows the failure notice instead of a dead panel", () => {
			cy.contains(".explorer-group", "Async items")
				.find('[aria-haspopup="menu"]')
				.eq(1)
				.click();

			cy.contains(".es-menu__item", "Fails to load").trigger("pointerenter");
			// the panel opens loading, then swaps to the inert notice
			cy.get(".es-menu[data-state='open']").should("have.length", 2);
			cy.contains(".es-menu__empty", "Couldn't load options").should("exist");
			// the root menu is still alive — Escape closes everything
			cy.focused().trigger("keydown", { key: "Escape" });
			cy.get(".es-menu[data-state='open']").should("not.exist");
		});
	});

	describe("Toast — legacy HTML message sanitisation", () => {
		// These lock in the harden() fix in ui/messages.js: xss_sanitise keeps
		// the tags, harden() strips code-running href/src schemes even when the
		// scheme hides behind an HTML-entity tab or a leading control char.

		it("strips a javascript: href hidden behind an HTML-entity tab", () => {
			cy.window().then((win) => {
				win.frappe.show_alert({
					// &#9; decodes to a tab: "java\tscript:", which the browser
					// runs as javascript: — harden must catch it
					message: 'safe <a class="probe" href="java&#9;script:alert(1)">x</a>',
					indicator: "blue",
				});
			});

			cy.get(".es-toast .probe").should("exist");
			cy.get(".es-toast .probe").should("not.have.attr", "href");
		});

		it("strips an on* handler attribute but keeps safe tags and hrefs", () => {
			cy.window().then((win) => {
				win.frappe.show_alert({
					message:
						'<strong class="ok-strong">Saved</strong> ' +
						'<a class="ok-link" href="/app/todo" onclick="alert(1)">open</a>',
					indicator: "green",
				});
			});

			// allowed markup survives
			cy.get(".es-toast .ok-strong").should("contain.text", "Saved");
			// a same-origin href is kept...
			cy.get(".es-toast .ok-link").should("have.attr", "href", "/app/todo");
			// ...but the inline handler is gone
			cy.get(".es-toast .ok-link").should("not.have.attr", "onclick");
		});
	});

	describe("Context Menu", () => {
		beforeEach(() => show("Context Menu"));

		it("opens at the pointer, marks the target data-state=open, and Escape closes + clears it", () => {
			cy.contains(".explorer-group", "Basic")
				.find(".explorer-preview")
				.children()
				.first()
				.as("surface");

			cy.get("@surface").rightclick();
			// the menu focuses its own panel on open (it's tabindex=-1), so
			// Escape closes it regardless of where the pointer is
			cy.get(".es-menu[data-state='open']").should("exist").and("have.focus");
			cy.get("@surface").should("have.attr", "data-state", "open");

			cy.focused().trigger("keydown", { key: "Escape" });
			cy.get(".es-menu[data-state='open']").should("not.exist");
			cy.get("@surface").should("not.have.attr", "data-state");
		});
	});

	describe("Tooltip", () => {
		beforeEach(() => show("Tooltip"));

		it("shows on hover with role=tooltip + aria-describedby, then hides on leave", () => {
			// the delay:0 example so we don't wait out the hover delay
			cy.contains(".es-button", "No delay").as("trigger");

			cy.get("@trigger").trigger("pointerenter", { pointerType: "mouse" });
			cy.get(".es-tooltip[role='tooltip']").should("exist");
			cy.get("@trigger").should("have.attr", "aria-describedby");

			cy.get("@trigger").trigger("pointerleave");
			cy.get(".es-tooltip").should("not.exist");
			cy.get("@trigger").should("not.have.attr", "aria-describedby");
		});
	});

	describe("Popover", () => {
		beforeEach(() => show("Popover"));

		it("opens a dialog, moves focus into it, and Escape closes + returns focus to the trigger", () => {
			cy.contains(".explorer-group", "Interactive content")
				.find('[aria-haspopup="dialog"]')
				.first()
				.as("trigger");

			cy.get("@trigger").click();
			cy.get(".es-popover[role='dialog'][data-state='open']")
				.should("exist")
				.and("have.focus");

			cy.get(".es-popover").trigger("keydown", { key: "Escape" });
			cy.get(".es-popover[data-state='open']").should("not.exist");
			cy.get("@trigger").should("have.focus");
		});
	});

	describe("Hover Card", () => {
		beforeEach(() => show("Hover Card"));

		it("opens on hover after the delay and closes on Escape", () => {
			// the open_delay:200 example (the default is 700ms)
			cy.contains("a", "Fast card").trigger("pointerenter", { pointerType: "mouse" });
			cy.get(".es-hover-card").should("exist");

			// the card holds no focus, so Escape is a document-level listener
			cy.get("body").trigger("keydown", { key: "Escape" });
			cy.get(".es-hover-card").should("not.exist");
		});
	});

	describe("Tabs", () => {
		beforeEach(() => show("Tabs"));

		it("switches the active panel on tab click, rendering lazy content", () => {
			cy.contains(".explorer-group", "Horizontal (arrows")
				.find(".es-tabs")
				.first()
				.within(() => {
					cy.contains(".es-tabs__tab", "Activity")
						.click()
						.should("have.attr", "aria-selected", "true");
					cy.get(".es-tabs__panel[data-state='active']").should(
						"contain.text",
						"Rendered lazily"
					);
				});
		});
	});

	describe("Tab Buttons", () => {
		beforeEach(() => show("Tab Buttons"));

		it("selects a pill on click (aria-checked) and unchecks the others", () => {
			cy.contains(".explorer-group", "Types")
				.find(".es-tab-buttons")
				.first()
				.within(() => {
					cy.contains(".es-pill", "In Progress")
						.click()
						.should("have.attr", "data-state", "active")
						.and("have.attr", "aria-checked", "true");
					cy.contains(".es-pill", "Open").should("have.attr", "aria-checked", "false");
				});
		});

		it("renders a disabled option as a disabled button", () => {
			cy.contains(".explorer-group", "Disabled options")
				.find(".es-tab-buttons")
				.first()
				.within(() => {
					cy.contains(".es-pill", "2500").should("be.disabled");
				});
		});
	});

	describe("Progress", () => {
		beforeEach(() => show("Progress"));

		it("exposes the value through aria and the hint text", () => {
			cy.contains(".explorer-group", "Basic (label")
				.find(".es-progress")
				.first()
				.within(() => {
					cy.get(".es-progress__track[role='progressbar']").should(
						"have.attr",
						"aria-valuenow",
						"30"
					);
					cy.get(".es-progress__hint").should("contain.text", "30%");
				});
		});

		it("fills the right number of interval segments for the value", () => {
			// value 50 across 6 segments -> round(50/100 * 6) = 3 filled
			cy.contains(".explorer-group", "Intervals")
				.find(".es-progress__track[data-intervals]")
				.first()
				.find(".es-progress__segment[data-filled]")
				.should("have.length", 3);
		});
	});

	describe("Combobox", () => {
		beforeEach(() => show("Combobox"));

		function trigger(group) {
			return cy.contains(".explorer-group", group).find(".es-combobox").first();
		}

		it("opens on click with the search focused, filters as you type, and picks with Enter", () => {
			trigger("Basic").as("trigger");
			cy.get("@trigger").click();
			cy.get(".es-combobox__panel[data-state='open']").should("exist");
			cy.focused().should("have.class", "es-combobox__input");

			cy.focused().type("pend");
			cy.get(".es-combobox__panel [role='option']").should("have.length", 1);
			cy.get(".es-combobox__panel [role='option'][data-highlighted]").should(
				"contain",
				"Pending Review"
			);

			cy.focused().type("{enter}");
			cy.get(".es-combobox__panel[data-state='open']").should("not.exist");
			cy.get("@trigger").should("contain", "Pending Review");
			// picking returns focus to the trigger
			cy.focused().should("have.class", "es-combobox");
		});

		it("ArrowDown moves the highlight, Escape closes and returns focus", () => {
			trigger("Basic").as("trigger");
			cy.get("@trigger").trigger("keydown", { key: "ArrowDown" });
			cy.get(".es-combobox__panel[data-state='open']").should("exist");
			cy.get(".es-combobox__panel [role='option'][data-highlighted]").should(
				"contain",
				"Open"
			);

			cy.focused().trigger("keydown", { key: "ArrowDown" });
			cy.get(".es-combobox__panel [role='option'][data-highlighted]").should(
				"contain",
				"Working"
			);

			cy.focused().trigger("keydown", { key: "Escape" });
			cy.get(".es-combobox__panel[data-state='open']").should("not.exist");
			cy.focused().should("have.class", "es-combobox");
		});

		it("typing on the closed trigger opens it with that query", () => {
			trigger("Basic").as("trigger");
			cy.get("@trigger").trigger("keydown", { key: "c" });
			cy.get(".es-combobox__input").should("have.value", "c");
			cy.get(".es-combobox__panel [role='option']")
				.should("have.length", 1)
				.and("contain", "Closed");
		});

		it("shows the create row highlighted when nothing matches", () => {
			trigger("Custom rows").click();
			cy.focused().type("zebra");
			cy.get(".es-combobox__panel .es-menu__empty").should("contain", "zebra");
			// the conditional Browse row hides itself while there is a query; Create stays
			cy.get(".es-combobox__footer [role='option']").should("have.length", 1);
			cy.get(".es-combobox__footer [role='option'][data-highlighted]").should(
				"contain",
				"Create a new Customer"
			);
		});

		it("loads the next page when the list is scrolled to its end", () => {
			trigger("Load more on scroll").click();
			cy.get(".es-combobox__panel [role='option']").should("have.length", 20);
			cy.get(".es-combobox__panel .es-menu__loading").should("exist");
			cy.get(".es-combobox__list").scrollTo("bottom");
			cy.get(".es-combobox__panel [role='option']").should("have.length", 40);
			// the rows that were on screen stay where they were
			cy.get(".es-combobox__panel [role='option']").first().should("contain", "Item 001");
		});

		it("keeps the filters to one line and expands to all of them on click", () => {
			// "Every operator" has many filters: the band shows the first + a count
			cy.contains(".explorer-group", "Applied filters").find(".es-combobox").eq(1).click();
			cy.get(".es-combobox__panel[data-state='open'] .es-combobox__filters")
				.as("band")
				.should("contain", "Filtered by")
				.find(".es-badge")
				.should("have.length", 2);
			cy.get("@band")
				.find(".es-badge")
				.eq(1)
				.invoke("text")
				.should("match", /^\+\d+$/);
			cy.get("@band").click();
			cy.get("@band").should("have.attr", "data-expanded");
			cy.get("@band").find(".es-badge").its("length").should("be.gt", 2);
			// the search box kept focus through the click
			cy.get(".es-combobox__panel[data-state='open'] .es-combobox__input").should(
				"have.focus"
			);
			// and back to one line
			cy.get("@band").click();
			cy.get("@band").should("not.have.attr", "data-expanded");
			cy.get("@band").find(".es-badge").should("have.length", 2);
			cy.get(".es-combobox__panel[data-state='open'] .es-combobox__input").type("{esc}");
		});

		it("has no search row when hide_search is set and clears via the × button", () => {
			trigger("No search row").as("trigger");
			cy.get("@trigger").should("contain", "Frappe Technologies");
			cy.get("@trigger").click();
			cy.get(".es-combobox__panel .es-combobox__input").should("not.exist");
			cy.get(".es-combobox__panel [role='option'][aria-selected='true']").should(
				"contain",
				"Frappe Technologies"
			);
			cy.focused().trigger("keydown", { key: "Escape" });

			cy.get("@trigger").find("[data-role='clear']").click({ force: true });
			cy.get("@trigger").find(".es-combobox__value").should("have.attr", "data-placeholder");
			// clearing reopens the panel for the next pick
			cy.get(".es-combobox__panel[data-state='open']")
				.should("exist")
				.trigger("keydown", { key: "Escape" });
			cy.get(".es-combobox__panel[data-state='open']").should("not.exist");
		});
	});
});
