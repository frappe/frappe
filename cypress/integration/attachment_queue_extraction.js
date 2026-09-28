// Covers frappe.attachment_queue_review.wait_for_extraction.
//
// It fakes the server's replies and the realtime socket,
// and it freezes time so the 90-second behaviour runs instantly.

context("Attachment Queue extraction wait", () => {
	const QUEUE_NAME = "test-attachment-queue";
	const TASK_ID = "task-under-test";
	const SLOW_THRESHOLD = 90000;
	const POLL_INTERVAL = 3000;

	before(() => {
		cy.login();
	});

	beforeEach(() => {
		// testIsolation is off, and these tests freeze timers and replace realtime handlers.
		cy.visit("/app/todo");
		cy.window()
			.its("frappe")
			.then((frappe) => frappe.attachment_queue_review_loader.load());
	});

	// Drives wait_for_extraction against a fake queue row whose status the test moves.
	function harness(win) {
		const state = {
			status: "Queued",
			resolved: null,
			rejected: null,
			settled: false,
			handlers: [],
			slow_calls: [],
			fetches: 0,
			controller: new win.AbortController(),
		};

		cy.stub(win.frappe.attachment_queue_review, "fetch_context").callsFake(() => {
			state.fetches += 1;
			return Promise.resolve({
				queue_name: QUEUE_NAME,
				task_id: TASK_ID,
				status: state.status,
			});
		});

		state.msgprint = cy.stub(win.frappe, "msgprint");

		win.frappe.realtime.on = (event, handler) => {
			if (event === "task_update") {
				state.handlers.push(handler);
			}
		};
		win.frappe.realtime.off = () => {};

		state.emit = (message) => state.handlers.forEach((handler) => handler(message));

		state.start = () => {
			win.frappe.attachment_queue_review
				.wait_for_extraction(
					{
						queue_name: QUEUE_NAME,
						task_id: TASK_ID,
						status: "Queued",
					},
					{
						signal: state.controller.signal,
						on_slow: (ctx) => state.slow_calls.push(ctx),
					}
				)
				.then((ctx) => {
					state.resolved = ctx;
					state.settled = true;
				})
				.catch((error) => {
					state.rejected = error;
					state.settled = true;
				});
		};

		return state;
	}

	it("T1: resolves on the Background Task 'Completed' event, with no warning", () => {
		cy.clock();
		cy.window().then((win) => {
			const state = harness(win);
			state.start();

			// The worker commits the row before it publishes, so the row is already terminal.
			state.status = "Ready for Review";
			state.emit({ task_id: TASK_ID, status: "Completed" });

			cy.wrap(state).its("resolved").should("have.property", "status", "Ready for Review");
			cy.then(() => {
				expect(state.msgprint, "no blocking warning").to.not.be.called;
				expect(state.slow_calls, "not reported as slow").to.have.length(0);
			});
		});
	});

	it("T2: does not report slow at the threshold when the row has already finished", () => {
		cy.clock();
		cy.window().then((win) => {
			const state = harness(win);
			state.start();

			state.status = "Ready for Review";
			cy.tick(SLOW_THRESHOLD);

			cy.wrap(state).its("resolved").should("have.property", "status", "Ready for Review");
			cy.then(() => {
				expect(state.msgprint, "no blocking warning").to.not.be.called;
				expect(state.slow_calls, "not reported as slow").to.have.length(0);
			});
		});
	});

	it("T3: reports slow at the threshold but keeps watching until the row finishes", () => {
		cy.clock();
		cy.window().then((win) => {
			const state = harness(win);
			state.start();

			state.status = "Processing";
			cy.tick(SLOW_THRESHOLD);

			// Still unsettled on purpose: the panel is not blocked on this wait.
			cy.wrap(state).its("slow_calls").should("have.length", 1);
			cy.then(() => {
				expect(state.slow_calls[0]).to.have.property("status", "Processing");
				expect(state.settled, "still watching").to.be.false;
				expect(state.msgprint, "no blocking warning").to.not.be.called;
			});

			cy.then(() => {
				state.status = "Ready for Review";
				state.emit({ task_id: TASK_ID, status: "Completed" });
			});
			cy.wrap(state).its("resolved").should("have.property", "status", "Ready for Review");
			cy.then(() => {
				expect(state.slow_calls, "reported slow only once").to.have.length(1);
			});
		});
	});

	it("T4: still resolves on a failed extraction", () => {
		cy.clock();
		cy.window().then((win) => {
			const state = harness(win);
			state.start();

			state.status = "Failed";
			state.emit({ task_id: TASK_ID, status: "Failed" });

			cy.wrap(state).its("resolved").should("have.property", "status", "Failed");
			cy.then(() => {
				expect(state.msgprint, "no blocking warning").to.not.be.called;
			});
		});
	});

	it("T5: ignores a 'Completed' event belonging to another task", () => {
		cy.clock();
		cy.window().then((win) => {
			const state = harness(win);
			state.start();

			// "Completed" is a common payload, so an unrelated task must not settle this wait.
			state.status = "Processing";
			state.emit({ task_id: "an-unrelated-task", status: "Completed" });
			cy.tick(POLL_INTERVAL);

			cy.wrap(state).should("have.property", "resolved", null);

			cy.then(() => {
				state.status = "Ready for Review";
				state.emit({ task_id: TASK_ID, status: "Completed" });
			});
			cy.wrap(state).its("resolved").should("have.property", "status", "Ready for Review");
		});
	});

	it("T6: keeps polling past the threshold, so a lost event still settles", () => {
		cy.clock();
		cy.window().then((win) => {
			// No task_update is ever emitted, so only the poll can settle this.
			const state = harness(win);
			state.start();

			state.status = "Processing";
			cy.tick(SLOW_THRESHOLD);
			cy.wrap(state).its("slow_calls").should("have.length", 1);

			cy.then(() => {
				state.status = "Ready for Review";
			});
			cy.tick(POLL_INTERVAL);

			cy.wrap(state).its("resolved").should("have.property", "status", "Ready for Review");
		});
	});

	it("T7: aborting resolves null and stops watching", () => {
		cy.clock();
		cy.window().then((win) => {
			const state = harness(win);
			state.start();

			state.status = "Processing";
			cy.tick(POLL_INTERVAL);

			cy.then(() => {
				state.controller.abort();
			});
			cy.wrap(state).should("have.property", "settled", true);

			cy.then(() => {
				expect(state.resolved, "resolves null, not a context").to.be.null;
				state.fetches_at_abort = state.fetches;
				// A row that finishes after the abort must not reach the caller.
				state.status = "Ready for Review";
			});
			cy.tick(SLOW_THRESHOLD + POLL_INTERVAL);
			cy.then(() => {
				expect(state.fetches, "no polling after abort").to.eq(state.fetches_at_abort);
				expect(state.resolved, "still null").to.be.null;
				expect(state.slow_calls, "no slow report after abort").to.have.length(0);
			});
		});
	});
});
