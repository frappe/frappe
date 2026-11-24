import assert from "node:assert/strict";
import test from "node:test";

import { askingAgain } from "../src/api/socket.js";

// a socket.io socket as the page sees it: `active` is false once the server refused it
function refusable() {
	const listeners = new Map();
	return {
		active: true,
		connects: 0,
		on: (name, fn) => listeners.set(name, fn),
		connect() {
			this.connects += 1;
		},
		disconnect() {},
		fail(active) {
			this.active = active;
			listeners.get("connect_error")(new Error("Unauthorized"));
		},
	};
}

test("a socket the relay refused asks again, until the page disconnects it", (t) => {
	t.mock.timers.enable({ apis: ["setTimeout"] });

	// a connection that could not be made: socket.io is still trying on its own
	const trying = askingAgain(refusable());
	trying.fail(true);
	t.mock.timers.tick(10_000);
	assert.equal(trying.connects, 0);

	// refused, as while the web server restarts: socket.io has stopped
	const refused = askingAgain(refusable());
	refused.fail(false);
	t.mock.timers.tick(3000);
	assert.equal(refused.connects, 1);
	refused.fail(false);
	t.mock.timers.tick(3000);
	assert.equal(refused.connects, 2);

	refused.fail(false);
	refused.disconnect();
	t.mock.timers.tick(10_000);
	assert.equal(refused.connects, 2);
});
