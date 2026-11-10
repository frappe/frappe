import assert from "node:assert/strict"
import test from "node:test"

import { findShortcut, SHORTCUTS } from "../src/shortcuts.js"

const event = (over = {}) => ({
	code: "KeyB",
	metaKey: false,
	altKey: false,
	shiftKey: false,
	ctrlKey: false,
	...over,
})

test("a combo needs Cmd or Ctrl and exact modifiers, and follows the typed character, else the key's place", () => {
	const [sidebar, workspace, settings] = SHORTCUTS
	for (const [over, shortcut] of [
		[{ metaKey: true }, sidebar],
		[{ ctrlKey: true }, sidebar],
		[{ metaKey: true, altKey: true }, workspace],
		[{ ctrlKey: true, code: "Comma" }, settings],
		[{}, null],
		[{ metaKey: true, shiftKey: true }, null],
		[{ metaKey: true, code: "KeyA" }, null],
		// Dvorak: the B key types x, so Cmd+X stays cut, and the key that types b is the shortcut
		[{ metaKey: true, key: "x" }, null],
		[{ metaKey: true, code: "KeyN", key: "b" }, sidebar],
		[{ ctrlKey: true, code: "KeyW", key: "," }, settings],
		// Option+B types "∫" on a mac, and a Cyrillic layout types "и": the key's place decides
		[{ metaKey: true, altKey: true, key: "∫" }, workspace],
		[{ ctrlKey: true, key: "и" }, sidebar],
	])
		assert.equal(findShortcut(event(over)), shortcut, JSON.stringify(over))
})
