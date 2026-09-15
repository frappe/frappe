// Desk's half of a Frappe UI page: the branch in `pageview.js` that builds the
// page, mounts the island named by the Page row, and sets the page head from
// what the island reports.
//
// The page under test is never inserted as a row. `getpage` is intercepted with
// the document a Frappe UI page returns, and the island is an ESM blob, so this
// spec covers desk's branch and neither the registry nor a real bundle. The
// registry, which turns a Page row into an island name, has its own tests in
// frappe/tests/test_island.py.

const PAGE = "cypress-island-page";
const ISLAND = `frappe.page.${PAGE}`;

const FIXTURE_MODULE = `
	export function mount(el, context) {
		const node = document.createElement("div");
		node.className = "page-island-fixture";
		el.appendChild(node);

		let props = { ...(context.props || {}) };
		const render = () => (node.textContent = (props.route || []).join("/"));
		render();

		props.onTitle?.("Reported Title");
		props.onActions?.([{ label: "Reported Action", onClick: () => (window.__action_ran = true) }]);

		return Promise.resolve({
			update(next) {
				props = { ...props, ...next };
				render();
			},
			unmount() {
				node.remove();
			},
		});
	}
`;

/** The document `getpage` returns for a Frappe UI page. */
function page_doc() {
	return {
		docs: [
			{
				doctype: "Page",
				name: PAGE,
				page_name: PAGE,
				title: "Page Title",
				module: "Desk",
				standard: "Yes",
				type: "Frappe UI",
				island: ISLAND,
				script: "",
				style: "",
				content: null,
			},
		],
	};
}

function register_island(win, { build = true } = {}) {
	if (build) {
		const url = win.URL.createObjectURL(
			new win.Blob([FIXTURE_MODULE], { type: "text/javascript" })
		);
		win.frappe.boot.assets_json[`${ISLAND}.island.js`] = url;
	}
	win.frappe.boot.ui_islands = { ...win.frappe.boot.ui_islands, [ISLAND]: ISLAND };
}

context("Frappe UI page", () => {
	before(() => {
		cy.login();
	});

	beforeEach(() => {
		cy.intercept("POST", "/api/method/frappe.desk.desk_page.getpage", {
			body: page_doc(),
		}).as("getpage");
	});

	function visit_page(options) {
		cy.visit("/app/website");
		cy.window().then((win) => {
			win.localStorage.removeItem(`_page:${PAGE}`);
			register_island(win, options);
			win.frappe.set_route(PAGE);
		});
		cy.wait("@getpage");
	}

	it("mounts the island the page names, inside the page content", () => {
		visit_page();
		cy.get(`#page-${PAGE} .page-content .page-island-fixture`).should("exist");
	});

	it("builds a page head, so the island draws no header of its own", () => {
		visit_page();
		cy.get(`#page-${PAGE} .page-head`).should("exist");
	});

	it("bounds the page, so the island scrolls its own body", () => {
		visit_page();
		cy.get("body").should("have.class", "island-page");
	});

	it("takes the page title from what the island reports", () => {
		visit_page();
		cy.title().should("include", "Reported Title");
	});

	it("fills the page menu from the actions the island reports", () => {
		visit_page();
		cy.get(`#page-${PAGE} .menu-btn-group`).click();
		cy.get(`#page-${PAGE} .menu-btn-group .dropdown-menu`).should(
			"contain",
			"Reported Action"
		);
	});

	it("hands the island the route below the page", () => {
		cy.visit("/app/website");
		cy.window().then((win) => {
			win.localStorage.removeItem(`_page:${PAGE}`);
			register_island(win);
			win.frappe.set_route(PAGE, "one", "two");
		});
		cy.wait("@getpage");
		cy.get(".page-island-fixture").should("have.text", "one/two");
	});

	it("updates the island in place when the route below the page moves", () => {
		visit_page();
		cy.get(".page-island-fixture").should("have.text", "");
		cy.window().then((win) => win.frappe.set_route(PAGE, "later"));
		cy.get(".page-island-fixture").should("have.text", "later");
	});

	it("says the page is unbuilt when its bundle is missing", () => {
		visit_page({ build: false });
		cy.get(`#page-${PAGE} .page-content`).should("contain", "has not been built");
	});
});
