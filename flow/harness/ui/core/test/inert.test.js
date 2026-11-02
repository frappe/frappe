import assert from "node:assert/strict"
import test from "node:test"

import { isPageEvent } from "../src/inert.js"

// a chat's element in an island's shadow root, and an event with the path it travelled
const island = (attrs = {}) => {
	const host = { hasAttribute: (name) => name in attrs }
	const el = { getRootNode: () => ({ host }) }
	return { host, el }
}
const event = (...path) => ({ composedPath: () => [...path, "window"] })

test("in a page's panel, an event from outside the chat's island is the page's", () => {
	const { host, el } = island({ "data-panel": "" })
	assert.equal(isPageEvent(event("deskInput", "body"), el), true)
	assert.equal(isPageEvent(event("body"), el), true)
	assert.equal(isPageEvent(event("textarea", host, "body"), el), false)
})

test("a chat that has the page to itself hears every event", () => {
	const { el } = island()
	assert.equal(isPageEvent(event("body"), el), false)
	assert.equal(isPageEvent(event("x"), { getRootNode: () => ({}) }), false)
	assert.equal(isPageEvent(event("x"), null), false)
})
