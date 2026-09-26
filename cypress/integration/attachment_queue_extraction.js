// Regression cover for `frappe.attachment_queue_review.wait_for_extraction`.
//
// `task_update` is Background Task's realtime event, so it carries Background Task's
// status vocabulary ("Completed"), not the queue row's ("Ready for Review"). Matching
// the queue row's names in the listener left the success path dead: the fallback poll of
// the day stood down on a healthy socket, so a successful extraction had no way to settle
// the promise before the 90s timer, which then warned "Extraction Still Running" about a
// row that had already finished. The poll is unconditional now, but the listener is still
// the thing that settles the normal case, so the cover stays.
//
// Nothing awaits this promise to show the preview any more — the panel renders from the
// queue row's source file and this only refreshes it — so the 90s mark no longer settles
// anything. It reports slowness and keeps watching (T3, T6).

context("Attachment Queue extraction wait", () => {
	const QUEUE_NAME = "test-attachment-queue";
	const TASK_ID = "task-under-test";
	const SLOW_THRESHOLD = 90000;
	const SLOW_POLL = 15000;

	before(() => {
		cy.login();
	});

	beforeEach(() => {
		// testIsolation is off for this suite, and these tests freeze timers and replace
		// realtime handlers — a fresh window per test keeps that from leaking forward.
		cy.visit("/app/todo");
		cy.window()
			.its("frappe")
			.then((frappe) => frappe.attachment_queue_review_loader.load());
	});

	// Drives wait_for_extraction against a fake queue row whose status the test moves,
	// standing in for the worker updating the row on the server.
	function harness(win, { socket_connected = true } = {}) {
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

		// Assigned rather than stubbed: these live on RealTimeClient.prototype, and the
		// fresh visit in beforeEach is what restores them.
		win.frappe.realtime.on = (event, handler) => {
			if (event === "task_update") {
				state.handlers.push(handler);
			}
		};
		win.frappe.realtime.off = () => {};

		// The bug only reproduces on a healthy socket: the 3s fallback poll stands down
		// whenever it is connected, leaving the realtime listener as the only thing that
		// can settle the promise before the slow threshold.
		win.frappe.realtime.socket = { connected: socket_connected };

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

			// The worker commits the row before it publishes, so the row is already
			// terminal by the time the event lands.
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

			// Finished after the immediate fetch, and no event ever arrives.
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

			// Reported once, and deliberately still unsettled: the panel is not blocked
			// on this, so a slow extraction is no reason to stop following it.
			cy.wrap(state).its("slow_calls").should("have.length", 1);
			cy.then(() => {
				expect(state.slow_calls[0]).to.have.property("status", "Processing");
				expect(state.settled, "still watching").to.be.false;
				expect(state.msgprint, "no blocking warning").to.not.be.called;
			});

			// The extraction it was still waiting for eventually lands.
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

			// "Completed" is a far more common payload than "Ready for Review" ever was,
			// so an unrelated background task must not settle this extraction.
			state.status = "Processing";
			state.emit({ task_id: "an-unrelated-task", status: "Completed" });
			cy.tick(3000);

			cy.wrap(state).should("have.property", "resolved", null);

			// The matching event still works, so the assertion above is not vacuous.
			cy.then(() => {
				state.status = "Ready for Review";
				state.emit({ task_id: TASK_ID, status: "Completed" });
			});
			cy.wrap(state).its("resolved").should("have.property", "status", "Ready for Review");
		});
	});

	it("T6: polls past the threshold on a healthy socket, so a lost event still settles", () => {
		cy.clock();
		cy.window().then((win) => {
			// Socket connected throughout, and no task_update is ever emitted: polling is
			// the only thing that can settle this, which is exactly why it runs regardless
			// of socket state.
			const state = harness(win, { socket_connected: true });
			state.start();

			state.status = "Processing";
			cy.tick(SLOW_THRESHOLD);
			cy.wrap(state).its("slow_calls").should("have.length", 1);

			cy.then(() => {
				state.status = "Ready for Review";
			});
			cy.tick(SLOW_POLL);

			cy.wrap(state).its("resolved").should("have.property", "status", "Ready for Review");
		});
	});

	it("T7: aborting resolves null and stops watching", () => {
		cy.clock();
		cy.window().then((win) => {
			const state = harness(win, { socket_connected: false });
			state.start();

			state.status = "Processing";
			cy.tick(3000);

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
			cy.tick(SLOW_THRESHOLD + SLOW_POLL);
			cy.then(() => {
				expect(state.fetches, "no polling after abort").to.eq(state.fetches_at_abort);
				expect(state.resolved, "still null").to.be.null;
				expect(state.slow_calls, "no slow report after abort").to.have.length(0);
			});
		});
	});
});
