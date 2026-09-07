// Regression cover for when the review panel is on screen and when it is not.
//
// The rule this suite holds in place: the panel belongs to the review, and the review
// ends with the link. It is up for as long as the reviewer is keying the document in,
// and it is gone once the save has linked the queue row — a submittable document's
// Submit page shows no preview at all, the source file is reached from the sidebar's
// own attachment preview instead. Two things could quietly break that: a refresh
// landing after the link and re-mounting from the Completed context, and the save's
// reroute not being seen as a document switch.
//
// Driven against a real ToDo form rather than a fake frm: the parts that matter here
// are framework parts — FormFactory's page-change, frm.refresh(), the stylesheet — so
// faking them would test the fakes.

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

		// Mount a review against the real form, the way route_to_new_document would.
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

			// State as it stands for the page-change that follows rename_notify: the panel
			// is still stamped with the local name the review was keyed in under. The
			// review ended with that save, so the panel goes with it.
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

	// The guard that makes "closed after save" deterministic. The context stays on the
	// saved document — get_pending_link reads it to refuse a second link on submit — so
	// without this a refresh landing after link_after_save would mount the panel again,
	// on the Submit page, from a row that has already given up its file.
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

	// The pre-save experience, which the panel's lifetime changes must not cost. The
	// shell is built once per source file, so a refresh mid-review leaves the iframe —
	// and the PDF it has already downloaded, at the page the reviewer scrolled to —
	// exactly where it was.
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

			// layout.js stamps these on *every* .form-tabs-list on the page whenever a form
			// tab is clicked. The panel borrows that class for its own strip, so the strip
			// has to be immune to a `top` measured against the page's scrollport.
			const $tabs = frm.attachment_queue_review_panel.find(".form-tabs-list");
			$tabs.addClass("form-tabs-sticky-up");

			const style = win.getComputedStyle($tabs.get(0));
			expect(style.position, "not sticky inside the panel").to.equal("relative");
			expect(style.top, "and no offset to push it down").to.equal("auto");
		});
	});

	// The preview's height comes from the viewport, never from the row. A grid row is
	// sized by its tallest item, so a panel that only capped its height inherited whatever
	// the form column made the row: the same PDF was tall on a long tab and short on a
	// collapsed one, and the viewer rescaled its page to match.
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

			// Collapsing a section is the cheapest way to change what the form column holds
			// without leaving the document. Its own outerHeight is not the precondition to
			// assert — the column stretches to the row now, so on a form shorter than the
			// viewport that number is the row's either way; what changed is the content.
			const $head = frm.$wrapper.find(".form-layout .section-head.collapsible").first();
			const $body = $head.next(".section-body");
			const body_before = $body.get(0)?.getBoundingClientRect().height;

			$head.trigger("click");

			expect(
				$body.get(0)?.getBoundingClientRect().height,
				"precondition: the section really did collapse"
			).to.not.equal(body_before);
			expect(panel_height(), "preview unmoved").to.be.closeTo(before, 2);

			// And the panel's own tab strip, which changes what the panel holds.
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

			// The preview sets the row now, so the form column has to take the rest of it —
			// otherwise a short form ends in page background next to a full-height preview.
			expect($form.outerHeight(), "form column fills the row").to.be.closeTo(
				$std.outerHeight(),
				2
			);
		});
	});

	// The preview track is an absolute length now. It used to be a percentage of
	// .std-form-layout, and that box is not a fixed thing: page.scss sizes
	// .layout-main-section-wrapper at 80% in general but calc(100% - the form sidebar)
	// on a form route, so the same stored width rendered differently depending on where
	// the reviewer had just been.
	it("T8: the preview column keeps its width when the container narrows", () => {
		cy.window().then((win) => {
			const frm = win.cur_frm;
			const panel_width = () =>
				frm.attachment_queue_review_panel.get(0).getBoundingClientRect().width;

			const before = panel_width();
			expect(before, "a real column to begin with").to.be.greaterThan(0);

			// What a route or sidebar change does to the container underneath the grid.
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

			// The form column's own content changing is the other half of the complaint.
			frm.$wrapper.find(".form-layout .section-head.collapsible").first().trigger("click");
			expect(panel_width(), "so does the form beside it").to.be.closeTo(before, 1);
		});
	});
});
