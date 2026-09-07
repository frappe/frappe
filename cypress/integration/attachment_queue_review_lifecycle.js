// Regression cover for where a review *session* ends, on both halves of the feature.
//
// The review ends with the save that links its queue row: the row reaches Completed and
// the panel comes down with it. What used to outlive that save was the *intent to link*.
// The loader's before_save re-armed a pending link from the Completed context on the
// submit that followed, and the one-shot guard it leant on (frm.doc.__attachment_queue_linked)
// had just been stripped by frappe.model.sync, so the submit re-called link_to_document and
// the server answered "is Completed and cannot be linked again". The modal had the mirror
// of the same fault: it kept its selection and its preview iframe between visits, so
// reopening it offered a finished review as though it were still actionable, and starting
// that produced a second document with no attachment — the source file having already moved
// to the first one.
//
// So the two ends are: the link session ends when the row reaches Completed, and the modal's
// session ends when the dialog hides.
//
// Driven against a real ToDo form and a real Dialog: the parts that matter are framework
// parts — the form's carriers across a save, the dialog's DOM outliving its visit — so
// faking them would test the fakes. EmbeddedList is the one thing stood in for; it has no
// part in what is under test here.

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
		// A real, saved document: the link session's whole question is what survives a
		// save, so a form that is still __islocal cannot exercise it.
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

		// Mounted through set_context, the same single writer hydrate_context uses in
		// production, so the context sits where the loader and the guards look for it.
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

	// The one line the loader's before_save runs. Kept as a helper because every test here
	// turns on what it computes.
	function before_save(win, frm) {
		frm.__attachment_queue_pending_link =
			win.frappe.attachment_queue_review.get_pending_link(frm) || null;
	}

	// What frappe.model.sync leaves behind on a save of an already-saved document:
	// update_in_locals' clear_keys deletes every key the server response does not carry,
	// which is every client-only __ property the review wrote. This is the state the
	// submit's after_save actually runs in.
	function sync_strips_doc_flags(frm) {
		delete frm.doc.__attachment_queue_review_context;
		delete frm.doc.__attachment_queue_linked;
		delete frm.doc.__attachment_queue_name;
	}

	// Answers only link_to_document, so the docinfo reload that follows a successful link
	// neither counts as a link nor gets a reply it cannot read.
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
		// EmbeddedList is not under test here — the selection and the preview are — so the
		// list is stood in for, which also shows that the reopen path re-reads it.
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

			// Submit. before_save runs first, while the Completed context is still on
			// frm.doc — the guard has to read it there, because the save that follows is
			// what strips it, and only then do after_save and on_submit reach
			// link_after_save with __attachment_queue_linked already gone.
			before_save(win, frm);
			expect(frm.__attachment_queue_pending_link, "no second link armed").to.be.null;

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

			// And the refresh that follows the save does not put it back. The context is
			// still on frm.doc — the guard in T1 reads it there — so this is mount()
			// refusing a finished review rather than simply finding nothing.
			expect(review.get_context(frm).status, "context still readable").to.equal("Completed");
			review.mount(frm);
			expect(frm.attachment_queue_review_panel, "and stays down").to.be.null;
		});
	});

	it("T2b: a link taken mid-extraction keeps the panel until extraction ends", () => {
		cy.window().then((win) => {
			const review = win.frappe.attachment_queue_review;
			const frm = win.cur_frm;

			// The save that claims a still-extracting row. The server accepts it — the
			// source file moves onto the document there and then — but answers with the
			// row's own transient status, because extraction is what ends the review.
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

			// The extracted text has nowhere else to appear, so the panel outlives the save.
			expect(frm.attachment_queue_review_panel, "panel survives the link").to.not.be.null;
			expect(review.get_context(frm).status, "status is not faked").to.equal("Processing");
			review.mount(frm);
			expect(frm.attachment_queue_review_panel, "and mount() keeps it").to.not.be.null;

			// The submit that follows must still not arm a second link: the row has already
			// produced its document, whatever its status says.
			before_save(win, frm);
			expect(frm.__attachment_queue_pending_link, "no second link armed").to.be.null;

			// Extraction ending is what ends the review.
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

				// The list row still says "Ready for Review"; the server says otherwise.
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

		// A different file in a rebuilt panel: nothing of the previous review is left.
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

			// The state a reopened document is in: no session in memory, and a finished
			// queue row still reachable through pending_context or ?attachment_queue=.
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

			// The upload-first flow starts a review on a row that is still Queued, and the
			// panel's copy of the status lags the worker. A stale "Queued" must not end the
			// link session: the server accepts that link and moves the source file onto the
			// document there and then.
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

			// What does end the link session is the row having produced its document —
			// which, for a link taken mid-extraction, arrives while the status is still
			// transient. Without this the submit would arm a second link against it.
			review.set_context(frm, {
				queue_name: QUEUE_NAME,
				document_type: "ToDo",
				status: "Processing",
				created_document: frm.doc.name,
				source_file: SOURCE_FILE,
				source_file_url: SOURCE_FILE,
			});

			expect(review.get_pending_link(frm), "already produced a document").to.be.null;

			// is_review_completed stays status-only: it governs the panel, not the link,
			// and the panel has to outlive a mid-extraction save so the extracted text
			// still has somewhere to land.
			expect(review.is_review_completed({ status: "Processing" })).to.be.false;
			expect(review.is_review_completed({ status: "Ready for Review" })).to.be.false;
			expect(review.is_review_completed({ status: "Completed" })).to.be.true;
		});
	});

	// The regression that lost the link outright. frm.doc is a cache of the review, not
	// its carrier: update_in_locals ends on clear_keys, which drops every client-only __
	// property the server response does not carry, and an ERPNext form makes several
	// doc-returning round trips while the reviewer keys the document in. The save that
	// follows must still link.
	it("T9: a sync that strips frm.doc still links on save", () => {
		cy.window().then((win) => {
			const review = win.frappe.attachment_queue_review;
			const frm = win.cur_frm;
			const calls = stub_link_call(win);

			// The URL the review has been carrying since it started.
			review.set_query_param("attachment_queue", QUEUE_NAME);

			// What clear_keys leaves behind, without the rest of a save.
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

			// The link is what ends the review, and the URL is where that is recorded.
			expect(
				win.frappe.utils.get_query_params().attachment_queue,
				"review closed on the URL too"
			).to.be.undefined;
			expect(review.get_pending_link(frm), "and nothing left to arm").to.be.null;
		});
	});

	// The other half of the same carrier: once the link has cleared the URL, a fetch that
	// was already in flight must not put the review back. It would re-stamp the param and
	// let the submit's before_save arm a second link against a Completed row.
	it("T10: a stale hydrate response cannot revive a finished review", () => {
		cy.window().then((win) => {
			const review = win.frappe.attachment_queue_review;
			const frm = win.cur_frm;

			review.set_query_param("attachment_queue", QUEUE_NAME);
			delete frm.doc.__attachment_queue_review_context;
			review.pending_context = null;

			// The race: hydrate reads the param, starts its fetch, and the link finishes
			// while that fetch is out. The reply describes the row as it was.
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
