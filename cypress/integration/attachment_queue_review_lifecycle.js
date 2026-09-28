// Covers when an Attachment Queue review ends, on the form and in the modal.
//
// On the form, the review ends when the save links the queue row. The panel closes, and
// the submit that follows must not link again, which the server would reject.
// In the modal, the review ends when the dialog closes. Reopening it must not show the old
// selection or preview.
//
// Uses a real ToDo form and a real Dialog, since those are what is being tested. Only
// EmbeddedList is stubbed.

context("Attachment Queue review lifecycle", () => {
	const QUEUE_NAME = "test-lifecycle-queue";
	const SOURCE_FILE = "/files/test-lifecycle-source.pdf";
	const NEXT_QUEUE = "test-lifecycle-queue-2";
	const NEXT_SOURCE = "/files/test-lifecycle-second.pdf";
	const MODAL_SCRIPT = "/assets/frappe/js/frappe/attachment_queue_review_modal.js";
	const NOT_REVIEWABLE = "Only documents that are ready for review can be reviewed.";

	before(() => {
		cy.login();
	});

	beforeEach(() => {
		// A saved document, since these tests check what survives a save.
		cy.insert_doc(
			"ToDo",
			{ description: "attachment queue review lifecycle cover" },
			true
		).then((doc) => {
			cy.visit("/app/todo/" + doc.name);
		});

		cy.window()
			.its("frappe")
			.then((frappe) => frappe.attachment_queue_review_loader.load());

		// Set the context the same way hydrate_context does.
		cy.window().then((win) => {
			const frm = win.cur_frm;
			win.frappe.attachment_queue_review.set_context(frm, {
				queue_name: QUEUE_NAME,
				document_type: "ToDo",
				status: "Ready for Review",
				source_file: SOURCE_FILE,
				source_file_url: SOURCE_FILE,
			});
			win.frappe.attachment_queue_review.mount(frm);
		});
	});

	// Same as the loader's before_save hook.
	function before_save(win, frm) {
		frm.__attachment_queue_pending_link =
			win.frappe.attachment_queue_review.get_pending_link(frm) || null;
	}

	// Saving a saved document removes the client-only __ keys from frm.doc
	// (frappe.model.sync). This does the same.
	function sync_strips_doc_flags(frm) {
		delete frm.doc.__attachment_queue_review_context;
		delete frm.doc.__attachment_queue_linked;
		delete frm.doc.__attachment_queue_name;
	}

	// Records only link_to_document calls. Other calls, like the docinfo reload after a
	// link, still get a reply but are not counted.
	function stub_link_call(win) {
		const calls = [];
		cy.stub(win.frappe, "call").callsFake((opts) => {
			if (opts.method && opts.method.endsWith("link_to_document")) {
				calls.push(opts);
				opts.callback && opts.callback({ message: { status: "Completed" } });
			}
			return Promise.resolve({ message: { status: "Completed" } });
		});
		return calls;
	}

	function build_modal(win) {
		const modal = new win.frappe.ui.AttachmentQueueModal({ doctype: "ToDo" });
		modal._build_screens();
		// EmbeddedList is not being tested, so stub it. The stub also lets tests check
		// that the list is refreshed.
		modal.list = { refresh: cy.stub() };
		return modal;
	}

	it("T1: the save links once, and the submit that follows does not link again", () => {
		cy.window().then((win) => {
			const review = win.frappe.attachment_queue_review;
			const frm = win.cur_frm;
			const calls = stub_link_call(win);

			// Save.
			before_save(win, frm);
			expect(frm.__attachment_queue_pending_link, "the save arms a link").to.not.be.null;
			review.link_after_save(frm);

			expect(calls, "linked once").to.have.length(1);
			expect(calls[0].args.attachment_queue).to.equal(QUEUE_NAME);
			expect(review.get_context(frm).status, "row is Completed").to.equal("Completed");

			// Submit. before_save still sees the Completed context, so it arms nothing.
			before_save(win, frm);
			expect(frm.__attachment_queue_pending_link, "no second link armed").to.be.null;

			// The save strips frm.doc. Then after_save and on_submit both run the link.
			sync_strips_doc_flags(frm);
			review.link_after_save(frm);
			review.link_after_save(frm);
			expect(calls, "still linked exactly once").to.have.length(1);
		});
	});

	it("T2: the panel comes down with the link", () => {
		cy.window().then((win) => {
			const review = win.frappe.attachment_queue_review;
			const frm = win.cur_frm;
			stub_link_call(win);

			expect(frm.attachment_queue_review_panel, "precondition: a panel is up").to.not.be
				.null;

			before_save(win, frm);
			review.link_after_save(frm);

			expect(frm.attachment_queue_review_panel, "torn down by the link").to.be.null;

			// The refresh after the save must not bring it back. The context is still
			// there, so this checks that mount() skips a Completed review.
			expect(review.get_context(frm).status, "context still readable").to.equal("Completed");
			review.mount(frm);
			expect(frm.attachment_queue_review_panel, "and stays down").to.be.null;
		});
	});

	it("T2b: a link taken mid-extraction keeps the panel until extraction ends", () => {
		cy.window().then((win) => {
			const review = win.frappe.attachment_queue_review;
			const frm = win.cur_frm;

			// The server accepts a link while extraction is running, and replies with the
			// row's current status.
			review.set_context(frm, {
				queue_name: QUEUE_NAME,
				document_type: "ToDo",
				status: "Processing",
				source_file: SOURCE_FILE,
				source_file_url: SOURCE_FILE,
			});
			review.mount(frm);

			cy.stub(win.frappe, "call").callsFake((opts) => {
				if (opts.method && opts.method.endsWith("link_to_document")) {
					opts.callback && opts.callback({ message: { status: "Processing" } });
				}
				return Promise.resolve({ message: { status: "Processing" } });
			});

			before_save(win, frm);
			review.link_after_save(frm);

			// The panel stays open so the extracted text can still show up.
			expect(frm.attachment_queue_review_panel, "panel survives the link").to.not.be.null;
			expect(review.get_context(frm).status, "status is not faked").to.equal("Processing");
			review.mount(frm);
			expect(frm.attachment_queue_review_panel, "and mount() keeps it").to.not.be.null;

			// The row already has its document, so the submit must not link again.
			before_save(win, frm);
			expect(frm.__attachment_queue_pending_link, "no second link armed").to.be.null;

			review.set_context(frm, { ...review.get_context(frm), status: "Completed" });
			review.mount(frm);
			expect(frm.attachment_queue_review_panel, "panel comes down with extraction").to.be
				.null;
		});
	});

	it("T3: a Completed queue cannot start a new review", () => {
		cy.window().then((win) => {
			const review = win.frappe.attachment_queue_review;
			review.pending_context = null;

			const msgprint = cy.stub(win.frappe, "msgprint");
			const set_route = cy.stub(win.frappe, "set_route").resolves();

			return review
				.route_to_new_document({
					queue_name: QUEUE_NAME,
					document_type: "ToDo",
					status: "Completed",
					created_document: win.cur_frm.doc.name,
					source_file: SOURCE_FILE,
					source_file_url: SOURCE_FILE,
				})
				.then(() => {
					expect(set_route, "no document opened").to.not.be.called;
					expect(msgprint, "says why").to.be.called;
					expect(review.pending_context, "no context handed over").to.be.null;
				});
		});
	});

	it("T4: Start Review turns down a row reviewed since the list was fetched", () => {
		cy.window().then((win) => {
			return win.frappe.require(MODAL_SCRIPT).then(() => {
				const review = win.frappe.attachment_queue_review;
				const modal = build_modal(win);

				// The list still shows "Ready for Review", but the server says Completed.
				cy.stub(review, "fetch_context").resolves({
					queue_name: QUEUE_NAME,
					document_type: "ToDo",
					status: "Completed",
					source_file: SOURCE_FILE,
					source_file_url: SOURCE_FILE,
				});
				const route = cy.stub(review, "route_to_new_document");
				const msgprint = cy.stub(win.frappe, "msgprint");
				const hide = cy.spy(modal.dialog, "hide");

				const row = {
					name: QUEUE_NAME,
					status: "Ready for Review",
					source_file: SOURCE_FILE,
				};
				modal.selected_row = row;
				modal._render_preview(row);
				expect(modal.$preview_content.find("iframe"), "precondition").to.have.length(1);

				return modal._start_review(row).then(() => {
					expect(route, "no review started").to.not.be.called;
					expect(msgprint, "says why").to.be.calledWith(NOT_REVIEWABLE);
					expect(modal.list.refresh, "list re-read instead").to.be.called;
					expect(hide, "modal left open").to.not.be.called;
					expect(modal.selected_row, "selection dropped").to.be.null;
					expect(
						modal.$preview_content.find("iframe"),
						"preview cleared"
					).to.have.length(0);
					expect(modal.$start_review_btn.prop("disabled"), "disarmed").to.be.true;
				});
			});
		});
	});

	it("T5: reopening the modal shows nothing from the review before it", () => {
		cy.window().then((win) => {
			return win.frappe.require(MODAL_SCRIPT).then(() => {
				const modal = build_modal(win);
				win.cy_modal = modal;

				modal.selected_row = { name: QUEUE_NAME, source_file: SOURCE_FILE };
				modal._render_preview(modal.selected_row);
				modal.show();
			});
		});

		cy.get(".aq-preview-content iframe").should("have.length", 1);

		cy.window().then((win) => win.cy_modal.dialog.hide());
		cy.get(".aq-preview-content iframe").should("have.length", 0);

		cy.window().then((win) => {
			expect(win.cy_modal.selected_row, "selection dropped on hide").to.be.null;
			win.cy_modal.show();
		});

		cy.get(".aq-preview-empty-container").should("exist");
		cy.window().then((win) => {
			const modal = win.cy_modal;
			expect(modal.$preview_content.find("iframe"), "no PDF carried over").to.have.length(0);
			expect(modal.$start_review_btn.prop("disabled"), "nothing to review yet").to.be.true;
			expect(modal.list.refresh, "the reopen re-read the list").to.be.called;
		});
	});

	it("T6: a genuinely new review mounts a fresh panel and can be linked", () => {
		cy.window().then((win) => {
			return win.frappe.attachment_queue_review.route_to_new_document({
				queue_name: NEXT_QUEUE,
				document_type: "ToDo",
				status: "Ready for Review",
				source_file: NEXT_SOURCE,
				source_file_url: NEXT_SOURCE,
			});
		});

		cy.get(".attachment-queue-review-panel iframe").should("have.attr", "src", NEXT_SOURCE);

		cy.window().then((win) => {
			const review = win.frappe.attachment_queue_review;
			const frm = win.cur_frm;

			expect(frm.is_new(), "a fresh document").to.be.true;
			expect(review.get_context(frm).queue_name, "the new queue").to.equal(NEXT_QUEUE);
			expect(review.get_pending_link(frm), "linkable").to.deep.equal({
				queue_name: NEXT_QUEUE,
				document_type: "ToDo",
			});
		});
	});

	it("T7: a finished review is not revived on the document it produced", () => {
		cy.window().then((win) => {
			const review = win.frappe.attachment_queue_review;
			const frm = win.cur_frm;

			// Like reopening the saved document: no context on the form, but
			// pending_context still holds the Completed row.
			review.teardown(frm);
			delete frm.doc.__attachment_queue_review_context;
			review.pending_context = {
				queue_name: QUEUE_NAME,
				document_type: "ToDo",
				status: "Completed",
				created_document: frm.doc.name,
				source_file: SOURCE_FILE,
				source_file_url: SOURCE_FILE,
			};

			return review.hydrate_context(frm).then(() => {
				expect(review.get_context(frm), "no session revived").to.be.null;
				review.mount(frm);
				expect(frm.attachment_queue_review_panel, "and no panel").to.be.null;
			});
		});
	});

	it("T8: a queue still extracting is not treated as finished", () => {
		cy.window().then((win) => {
			const review = win.frappe.attachment_queue_review;
			const frm = win.cur_frm;

			// The panel's status can be behind the worker. A row that is still Queued can
			// be linked, since the server accepts it.
			review.set_context(frm, {
				queue_name: QUEUE_NAME,
				document_type: "ToDo",
				status: "Queued",
				source_file: SOURCE_FILE,
				source_file_url: SOURCE_FILE,
			});

			expect(review.get_pending_link(frm), "still linkable").to.deep.equal({
				queue_name: QUEUE_NAME,
				document_type: "ToDo",
			});

			// Once the row has a created_document it must not be linked again, even while
			// extraction is still running.
			review.set_context(frm, {
				queue_name: QUEUE_NAME,
				document_type: "ToDo",
				status: "Processing",
				created_document: frm.doc.name,
				source_file: SOURCE_FILE,
				source_file_url: SOURCE_FILE,
			});

			expect(review.get_pending_link(frm), "already produced a document").to.be.null;

			// is_review_completed checks the status only. It decides when the panel closes,
			// and the panel stays open during extraction.
			expect(review.is_review_completed({ status: "Processing" })).to.be.false;
			expect(review.is_review_completed({ status: "Ready for Review" })).to.be.false;
			expect(review.is_review_completed({ status: "Completed" })).to.be.true;
		});
	});

	// Every sync removes the __ keys from frm.doc, and ERPNext forms sync several times
	// while the user fills them in. The save must still link, using the URL.
	it("T9: a sync that strips frm.doc still links on save", () => {
		cy.window().then((win) => {
			const review = win.frappe.attachment_queue_review;
			const frm = win.cur_frm;
			const calls = stub_link_call(win);

			// The review keeps the queue name in the URL.
			review.set_query_param("attachment_queue", QUEUE_NAME);

			delete frm.doc.__attachment_queue_review_context;
			expect(review.get_context(frm), "context gone, as after a sync").to.be.null;

			before_save(win, frm);
			expect(
				frm.__attachment_queue_pending_link,
				"the save still arms a link"
			).to.deep.equal({ queue_name: QUEUE_NAME, document_type: "ToDo" });

			review.link_after_save(frm);

			expect(calls, "linked once").to.have.length(1);
			expect(calls[0].args.attachment_queue).to.equal(QUEUE_NAME);
			expect(calls[0].args.document_name).to.equal(frm.doc.name);

			expect(
				win.frappe.utils.get_query_params().attachment_queue,
				"review closed on the URL too"
			).to.be.undefined;
			expect(review.get_pending_link(frm), "and nothing left to arm").to.be.null;
		});
	});

	// After a link clears the URL, a fetch that started before it must not bring the
	// review back. Otherwise the submit would link again.
	it("T10: a stale hydrate response cannot revive a finished review", () => {
		cy.window().then((win) => {
			const review = win.frappe.attachment_queue_review;
			const frm = win.cur_frm;

			review.set_query_param("attachment_queue", QUEUE_NAME);
			delete frm.doc.__attachment_queue_review_context;
			review.pending_context = null;

			// The link finishes while hydrate is waiting for its fetch, so the reply is
			// out of date.
			cy.stub(review, "fetch_context").callsFake(() => {
				review.clear_query_param("attachment_queue");
				return Promise.resolve({
					queue_name: QUEUE_NAME,
					document_type: "ToDo",
					status: "Ready for Review",
					source_file: SOURCE_FILE,
					source_file_url: SOURCE_FILE,
				});
			});

			return review.hydrate_context(frm).then(() => {
				expect(review.get_context(frm), "stale reply dropped").to.be.null;
				expect(
					win.frappe.utils.get_query_params().attachment_queue,
					"and the URL stays closed"
				).to.be.undefined;
				expect(review.get_pending_link(frm), "so the submit arms nothing").to.be.null;

				review.mount(frm);
				expect(frm.attachment_queue_review_panel, "and no panel comes back").to.be.null;
			});
		});
	});
});
