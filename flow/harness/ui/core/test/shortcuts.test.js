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

test("cmd+b matches the sidebar shortcut", () => {
	assert.equal(findShortcut(event({ metaKey: true })), SHORTCUTS[0])
})

test("cmd+option+b matches the workspace shortcut", () => {
	assert.equal(findShortcut(event({ metaKey: true, altKey: true })), SHORTCUTS[1])
})

test("modifiers must match exactly", () => {
	assert.equal(findShortcut(event()), null)
	assert.equal(findShortcut(event({ metaKey: true, shiftKey: true })), null)
	assert.equal(findShortcut(event({ metaKey: true, ctrlKey: true })), null)
	assert.equal(findShortcut(event({ metaKey: true, code: "KeyA" })), null)
})
