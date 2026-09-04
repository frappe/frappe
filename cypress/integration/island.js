// Desk's half of the island seam: `frappe.ui.mount_island`.
//
// The island under test is a fixture the browser builds — an ESM blob registered
// in `frappe.boot.assets_json` under the `.island.js` key convention and declared
// in `frappe.boot.ui_islands`, as a real app's build and hooks.py would do. It is
// self-contained, the way a built island is, so this spec covers framework's seam
// and no app's bundle.
//
// What the island then does with the context — the shadow root, the Vue app, the
// theme — is the mount contract in `ui/island/`, and is verified where it is
// built.

const ISLAND = "frappe.cypress_fixture";
const BUNDLE = "cypress_fixture";

const FIXTURE_MODULE = `
	export function mount(el, context) {
		window.__island_mounts = (window.__island_mounts || 0) + 1;
		window.__island_context = context;

		const host = document.createElement("div");
		host.className = "fixture-island";
		el.appendChild(host);

		const root = host.attachShadow({ mode: "open" });
		const node = document.createElement("div");
		node.className = "fixture";
		root.append(node);

		let props = { ...(context.props || {}) };
		const render = () => (node.textContent = props.label || "");
		render();

		context.props?.onReady?.(context.host);

		return Promise.all((context.styles || []).map(adopt)).then((sheets) => {
			root.adoptedStyleSheets = sheets;
			return {
				update(next) {
					props = { ...props, ...next };
					render();
				},
				unmount() {
					window.__island_unmounts = (window.__island_unmounts || 0) + 1;
					host.remove();
				},
			};
		});
	}

	function adopt(url) {
		return fetch(url)
			.then((response) => response.text())
			.then((css) => {
				const sheet = new CSSStyleSheet();
				sheet.replaceSync(css);
				return sheet;
			});
	}
`;

const FIXTURE_CSS = `.fixture { color: rgb(1, 2, 3); }`;

function blob_url(win, source, type) {
	return win.URL.createObjectURL(new win.Blob([source], { type }));
}

function register_fixture(win) {
	win.frappe.boot.assets_json[`${BUNDLE}.island.js`] = blob_url(
		win,
		FIXTURE_MODULE,
		"text/javascript"
	);
	win.frappe.boot.assets_json[`${BUNDLE}.island.css`] = blob_url(win, FIXTURE_CSS, "text/css");
	win.frappe.boot.ui_islands = { ...win.frappe.boot.ui_islands, [ISLAND]: BUNDLE };
}

function host_element(win, id) {
	const el = win.document.createElement("div");
	el.id = id;
	win.document.querySelector("#body").appendChild(el);
	return el;
}

const shadow_text = (el) =>
	el.querySelector(".fixture-island").shadowRoot.querySelector(".fixture").textContent;

context("Island", () => {
	before(() => {
		cy.login();
	});

	beforeEach(() => {
		cy.visit("/app/website");
		cy.window().then((win) => {
			register_fixture(win);
			win.__island_mounts = 0;
			win.__island_unmounts = 0;
		});
	});

	it("resolves a declared name and mounts what it names", () => {
		cy.window().then((win) => {
			const el = host_element(win, "island-1");
			return win.frappe.ui.mount_island(ISLAND, el, { label: "hello" }).ready.then(() => {
				expect(win.__island_mounts).to.equal(1);
				expect(shadow_text(el)).to.equal("hello");
			});
		});
	});

	it("hands the island desk's context", () => {
		cy.window().then((win) => {
			const el = host_element(win, "island-2");
			return win.frappe.ui.mount_island(ISLAND, el, {}).ready.then(() => {
				const host = win.__island_context.host;
				expect(host.user).to.equal(win.frappe.session.user);
				expect(host.locale).to.be.a("string");
				expect(host.base_url).to.be.a("string");
				expect(host.navigate).to.be.a("function");
			});
		});
	});

	it("hands the island its own stylesheet", () => {
		cy.window().then((win) => {
			const el = host_element(win, "island-3");
			return win.frappe.ui.mount_island(ISLAND, el, {}).ready.then(() => {
				expect(win.__island_context.styles).to.deep.equal([
					win.frappe.boot.assets_json[`${BUNDLE}.island.css`],
				]);
				const root = el.querySelector(".fixture-island").shadowRoot;
				expect(root.adoptedStyleSheets[0].cssRules[0].selectorText).to.equal(".fixture");
			});
		});
	});

	it("hands the island the listeners in its props", () => {
		cy.window().then((win) => {
			const el = host_element(win, "island-4");
			const ready = cy.stub();
			return win.frappe.ui.mount_island(ISLAND, el, { onReady: ready }).ready.then(() => {
				expect(ready).to.have.been.calledOnce;
			});
		});
	});

	it("update(props) reaches the island without re-mounting it", () => {
		cy.window().then((win) => {
			const el = host_element(win, "island-5");
			return win.frappe.ui
				.mount_island(ISLAND, el, { label: "before" })
				.ready.then((island) => {
					island.update({ label: "after" });
					expect(shadow_text(el)).to.equal("after");
					expect(win.__island_mounts).to.equal(1);
				});
		});
	});

	it("unmounts idempotently", () => {
		cy.window().then((win) => {
			const el = host_element(win, "island-6");
			return win.frappe.ui.mount_island(ISLAND, el, {}).ready.then((island) => {
				island.unmount();
				island.unmount();
				expect(win.__island_unmounts).to.equal(1);
				expect(el.querySelector(".fixture-island")).to.be.null;
			});
		});
	});

	it("replaces the island already in a target", () => {
		cy.window().then((win) => {
			const el = host_element(win, "island-7");
			return win.frappe.ui
				.mount_island(ISLAND, el, { label: "first" })
				.ready.then(
					() => win.frappe.ui.mount_island(ISLAND, el, { label: "second" }).ready
				)
				.then(() => {
					expect(win.__island_unmounts).to.equal(1);
					expect(el.querySelectorAll(".fixture-island")).to.have.length(1);
					expect(shadow_text(el)).to.equal("second");
				});
		});
	});

	it("explains an island name no app declares", () => {
		cy.window().then((win) => {
			const el = host_element(win, "island-8");
			return win.frappe.ui.mount_island("nosuchapp.nosuchisland", el, {}).ready.then(
				() => {
					throw new Error("expected mount_island to reject");
				},
				(e) => {
					expect(e.message).to.contain("ui_islands");
				}
			);
		});
	});

	it("explains a declared island whose app has not been built", () => {
		cy.window().then((win) => {
			const el = host_element(win, "island-9");
			win.frappe.boot.ui_islands["frappe.unbuilt"] = "unbuilt_fixture";
			return win.frappe.ui.mount_island("frappe.unbuilt", el, {}).ready.then(
				() => {
					throw new Error("expected mount_island to reject");
				},
				(e) => {
					expect(e.message).to.contain("assets.json");
				}
			);
		});
	});

	it("leaves classic bundles on the page working", () => {
		cy.window().then((win) => {
			const el = host_element(win, "island-10");
			return win.frappe.ui
				.mount_island(ISLAND, el, {})
				.ready.then(() => win.frappe.require("dialog.bundle.js"))
				.then(() => {
					const dialog = new win.frappe.ui.Dialog({ title: "classic" });
					dialog.show();
					expect(dialog.$wrapper.find(".modal-title").text()).to.contain("classic");
					dialog.hide();
				});
		});
	});
});
