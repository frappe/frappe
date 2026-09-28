// Covers when the review panel is shown on the form, and its size and layout.
//
// The panel stays while the user fills in the document, and goes away once the save
// links the queue row. After that, the source file is shown in the sidebar instead.
//
// Uses a real ToDo form, since the page change, refresh and CSS are what is being tested.

context("Attachment Queue review panel visibility", () => {
	const QUEUE_NAME = "test-attachment-queue";
	const SOURCE_FILE = "/files/test-review-source.pdf";

	before(() => {
		cy.login();
	});

	beforeEach(() => {
		cy.insert_doc("ToDo", { description: "attachment queue review panel cover" }, true).then(
			(doc) => {
				cy.visit(`/app/todo/${doc.name}`);
			}
		);

		cy.window()
			.its("frappe")
			.then((frappe) => frappe.attachment_queue_review_loader.load());

		// Start a review on this form.
		cy.window().then((win) => {
			const frm = win.cur_frm;
			frm.doc.__attachment_queue_review_context = {
				queue_name: QUEUE_NAME,
				document_type: "ToDo",
				status: "Ready for Review",
				source_file: SOURCE_FILE,
				source_file_url: SOURCE_FILE,
			};
			win.frappe.attachment_queue_review.mount(frm);
		});
	});

	function layout(win) {
		return win.cur_frm.$wrapper.find(".form-layout").first().closest(".std-form-layout");
	}

	it("T1: routing to a different document tears the panel down", () => {
		cy.window().then((win) => {
			const frm = win.cur_frm;
			frm.attachment_queue_review_panel_docname = frm.docname;

			cy.stub(win.frappe, "get_route").returns(["Form", "ToDo", "some-other-todo"]);
			win.frappe.attachment_queue_review.clear_switched_panels();

			expect(frm.attachment_queue_review_panel, "panel is destroyed").to.be.null;
			expect(layout(win).hasClass("attachment-queue-review-layout")).to.be.false;
		});
	});

	it("T2: the reroute from the local name to the saved name is a switch too", () => {
		cy.window().then((win) => {
			const frm = win.cur_frm;

			// After the first save, the route changes from the "new-todo-..." name to the
			// saved name. The panel still has the old name, and the save ended the review,
			// so the panel is removed.
			frm.attachment_queue_review_panel_docname = "new-todo-abc1234567";

			cy.stub(win.frappe, "get_route").returns(["Form", "ToDo", frm.docname]);
			win.frappe.attachment_queue_review.clear_switched_panels();

			expect(frm.attachment_queue_review_panel, "panel is destroyed").to.be.null;
		});
	});

	it("T3: linking on save tears the panel down", () => {
		cy.window().then((win) => {
			const frm = win.cur_frm;

			frm.__attachment_queue_pending_link = {
				queue_name: QUEUE_NAME,
				document_type: "ToDo",
			};

			cy.stub(win.frappe, "call").callsFake((opts) => {
				opts.callback && opts.callback({ message: { status: "Completed" } });
				return Promise.resolve({ message: { status: "Completed" } });
			});

			win.frappe.attachment_queue_review.link_after_save(frm);

			expect(frm.attachment_queue_review_panel, "panel ends with the review").to.be.null;
			expect(layout(win).hasClass("attachment-queue-review-layout")).to.be.false;
			expect(layout(win).find(".attachment-queue-review-panel").length).to.equal(0);
		});
	});

	// The context stays on the saved document so a second link can be refused on submit.
	// So mount() must skip a Completed review, or a later refresh would show the panel again.
	it("T4: a refresh after the link does not bring the panel back", () => {
		cy.window().then((win) => {
			const frm = win.cur_frm;
			const review = win.frappe.attachment_queue_review;

			review.set_context(frm, {
				queue_name: QUEUE_NAME,
				document_type: "ToDo",
				status: "Completed",
				created_document: frm.docname,
				source_file: SOURCE_FILE,
				source_file_url: SOURCE_FILE,
			});

			review.mount(frm);

			expect(frm.attachment_queue_review_panel, "no panel for a finished review").to.be.null;
			expect(layout(win).hasClass("attachment-queue-review-layout")).to.be.false;
		});
	});

	// The panel is built once per source file, so a refresh keeps the same iframe and the
	// PDF stays on the page the user scrolled to.
	it("T5: a refresh mid-review reuses the same iframe node and src", () => {
		cy.window().then((win) => {
			const frm = win.cur_frm;
			const review = win.frappe.attachment_queue_review;
			const iframe_before = frm.attachment_queue_review_panel.find("iframe").get(0);
			const src_before = iframe_before.getAttribute("src");

			expect(iframe_before, "the panel renders a PDF iframe").to.exist;

			review.mount(frm);
			review.mount(frm);

			const iframe_after = frm.attachment_queue_review_panel.find("iframe").get(0);
			expect(iframe_after, "same iframe node").to.equal(iframe_before);
			expect(iframe_after.getAttribute("src"), "src untouched").to.equal(src_before);
			expect(frm.attachment_queue_review_panel.is(":visible"), "still on screen").to.be.true;
		});
	});

	it("T6: core's global sticky-tab classes do not move the panel's tab strip", () => {
		cy.window().then((win) => {
			const frm = win.cur_frm;

			// layout.js adds this class to every .form-tabs-list when a form tab is clicked.
			// The panel's tab strip uses the same class, so it must not become sticky.
			const $tabs = frm.attachment_queue_review_panel.find(".form-tabs-list");
			$tabs.addClass("form-tabs-sticky-up");

			const style = win.getComputedStyle($tabs.get(0));
			expect(style.position, "not sticky inside the panel").to.equal("relative");
			expect(style.top, "and no offset to push it down").to.equal("auto");
		});
	});

	// The preview height should follow the viewport, not the form beside it. Otherwise the
	// same PDF is tall next to a long form and short next to a short one.
	function head_height(win) {
		return parseFloat(
			win
				.getComputedStyle(win.document.documentElement)
				.getPropertyValue("--page-head-height")
		);
	}

	it("T7: the preview height is the viewport's, not the form's", () => {
		cy.window().then((win) => {
			const frm = win.cur_frm;
			const panel = frm.attachment_queue_review_panel.get(0);

			expect(
				panel.getBoundingClientRect().height,
				"one viewport, less the page head"
			).to.be.closeTo(win.innerHeight - head_height(win), 2);
		});
	});

	it("T7b: tab and section changes leave the preview height alone", () => {
		cy.window().then((win) => {
			const frm = win.cur_frm;
			const panel_height = () =>
				frm.attachment_queue_review_panel.get(0).getBoundingClientRect().height;

			const before = panel_height();

			// Collapse a section to change the form's content. Check the section body, since
			// the form column always fills the row.
			const $head = frm.$wrapper.find(".form-layout .section-head.collapsible").first();
			const $body = $head.next(".section-body");
			const body_before = $body.get(0)?.getBoundingClientRect().height;

			$head.trigger("click");

			expect(
				$body.get(0)?.getBoundingClientRect().height,
				"precondition: the section really did collapse"
			).to.not.equal(body_before);
			expect(panel_height(), "preview unmoved").to.be.closeTo(before, 2);

			frm.attachment_queue_review_panel.find(".form-tabs-list .nav-link").each((_, el) => {
				win.$(el).trigger("click");
			});
			win.frappe.attachment_queue_review.set_active_tab(frm, "preview");
			expect(panel_height(), "and unmoved across the preview's own tabs").to.be.closeTo(
				before,
				2
			);
		});
	});

	it("T7c: the form column fills the row, so there is no band beside the preview", () => {
		cy.window().then((win) => {
			const $std = layout(win);
			const $form = $std.children(".form-layout");

			expect($form.outerHeight(), "form column fills the row").to.be.closeTo(
				$std.outerHeight(),
				2
			);
		});
	});

	// The preview width is a fixed length, not a percentage of the form layout. The
	// layout's width changes between routes, so a percentage made the preview jump.
	it("T8: the preview column keeps its width when the container narrows", () => {
		cy.window().then((win) => {
			const frm = win.cur_frm;
			const panel_width = () =>
				frm.attachment_queue_review_panel.get(0).getBoundingClientRect().width;

			const before = panel_width();
			expect(before, "a real column to begin with").to.be.greaterThan(0);

			// Narrow the container, like a route or sidebar change does.
			const $wrapper = frm.page.wrapper.find(".layout-main-section-wrapper");
			const layout_before = layout(win).get(0).getBoundingClientRect().width;
			$wrapper.css("width", "70%");
			expect(
				layout(win).get(0).getBoundingClientRect().width,
				"precondition: the container really did change"
			).to.be.lessThan(layout_before);

			expect(panel_width(), "preview column unmoved").to.be.closeTo(before, 1);

			$wrapper.css("width", "");
			expect(panel_width(), "and unmoved on the way back").to.be.closeTo(before, 1);
		});
	});

	it("T9: tab and form-section changes do not resize the preview column", () => {
		cy.window().then((win) => {
			const frm = win.cur_frm;
			const review = win.frappe.attachment_queue_review;
			const panel_width = () =>
				frm.attachment_queue_review_panel.get(0).getBoundingClientRect().width;

			const before = panel_width();

			frm.attachment_queue_review_panel.find(".form-tabs-list .nav-link").each((_, el) => {
				win.$(el).trigger("click");
			});
			review.set_active_tab(frm, "preview");
			expect(panel_width(), "tabs leave it alone").to.be.closeTo(before, 1);

			frm.$wrapper.find(".form-layout .section-head.collapsible").first().trigger("click");
			expect(panel_width(), "so does the form beside it").to.be.closeTo(before, 1);
		});
	});
});
