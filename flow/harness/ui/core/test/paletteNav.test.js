import assert from "node:assert/strict"
import test from "node:test"

import { nextNavigationIndex } from "../src/paletteNav.js"

test("list navigation wraps, starts at the nearest edge, and leaves other keys and empty lists alone", () => {
	for (const [current, count, key, next] of [
		[0, 3, "ArrowUp", 2],
		[2, 3, "ArrowDown", 0],
		[1, 3, "ArrowDown", 2],
		// nothing active yet
		[-1, 3, "ArrowDown", 0],
		[-1, 3, "ArrowUp", 2],
		[0, 3, "Home", null],
		[0, 0, "ArrowDown", null],
	])
		assert.equal(nextNavigationIndex(current, count, key), next, `${key} from ${current} of ${count}`)
})
