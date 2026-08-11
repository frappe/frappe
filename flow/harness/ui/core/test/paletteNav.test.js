import assert from "node:assert/strict"
import test from "node:test"

import { nextNavigationIndex } from "../src/paletteNav.js"

test("list navigation wraps in both directions", () => {
	assert.equal(nextNavigationIndex(0, 3, "ArrowUp"), 2)
	assert.equal(nextNavigationIndex(2, 3, "ArrowDown"), 0)
	assert.equal(nextNavigationIndex(1, 3, "ArrowDown"), 2)
})

test("list navigation starts at the nearest edge when nothing is active", () => {
	assert.equal(nextNavigationIndex(-1, 3, "ArrowDown"), 0)
	assert.equal(nextNavigationIndex(-1, 3, "ArrowUp"), 2)
})

test("unrelated keys and empty lists are left alone", () => {
	assert.equal(nextNavigationIndex(0, 0, "ArrowDown"), null)
	assert.equal(nextNavigationIndex(0, 3, "Home"), null)
	assert.equal(nextNavigationIndex(0, 3, "Enter"), null)
})
