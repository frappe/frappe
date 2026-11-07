import assert from "node:assert/strict"
import test from "node:test"

import { STRAY_DROPS, dragDepth, dragHasFiles } from "../src/fileDrop.js"

test("only a drag that carries files is a file drop", () => {
	assert.equal(dragHasFiles({ dataTransfer: { types: ["Files"] } }), true)
	assert.equal(dragHasFiles({ dataTransfer: { types: ["text/plain", "text/uri-list"] } }), false)
	assert.equal(dragHasFiles({}), false)
})

test("a drag stays over the chat while it crosses the chat's children", () => {
	const depth = dragDepth()
	assert.equal(depth.enter(), true) // the chat
	assert.equal(depth.enter(), true) // the box inside it
	assert.equal(depth.leave(), true) // off the box, still on the chat
	assert.equal(depth.leave(), false) // off the chat
	assert.equal(depth.leave(), false) // a stray leave does not go below zero
	assert.equal(depth.enter(), true)
	depth.reset() // a drop ends it
	assert.equal(depth.leave(), false)
})

test("a file drag where nothing takes it is caught, unless the chat took it", () => {
	const drag = (types, handled = false) => {
		const event = {
			dataTransfer: { types, dropEffect: "copy" },
			defaultPrevented: handled,
			preventDefault() {
				this.defaultPrevented = true
			},
		}
		return event
	}
	const stray = drag(["Files"])
	STRAY_DROPS.dragover(stray)
	assert.equal(stray.defaultPrevented, true)
	assert.equal(stray.dataTransfer.dropEffect, "none")

	const taken = drag(["Files"], true)
	STRAY_DROPS.dragover(taken)
	assert.equal(taken.dataTransfer.dropEffect, "copy")

	const text = drag(["text/plain"])
	STRAY_DROPS.drop(text)
	assert.equal(text.defaultPrevented, false)
})
