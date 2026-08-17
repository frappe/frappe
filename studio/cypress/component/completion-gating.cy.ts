import { setActivePinia } from "pinia"
import { EditorState } from "@codemirror/state"
import { CompletionContext } from "@codemirror/autocomplete"
import { ensureSyntaxTree } from "@codemirror/language"
import { javascript } from "@codemirror/lang-javascript"
import {
	isInsideDynamicValue,
	isInsideFunctionExpression,
	useDynamicValueCompletions,
} from "@/utils/useStudioCompletions"
import { pinia } from "../support/component"

// "|" marks the cursor position
function contextAt(docWithCursor: string): CompletionContext {
	const pos = docWithCursor.indexOf("|")
	const doc = docWithCursor.slice(0, pos) + docWithCursor.slice(pos + 1)
	const state = EditorState.create({ doc, extensions: [javascript()] })
	ensureSyntaxTree(state, doc.length, 5000)
	return new CompletionContext(state, pos, false)
}

describe("prop editor completion gating", () => {
	describe("isInsideDynamicValue", () => {
		it("is false in static text", () => {
			expect(isInsideDynamicValue(contextAt('{ icon: "sta|r" }'))).to.be.false
		})

		it("is true inside a closed {{ }}", () => {
			expect(isInsideDynamicValue(contextAt("{{ getIc| }}"))).to.be.true
		})

		it("is true inside an unclosed {{ still being typed", () => {
			expect(isInsideDynamicValue(contextAt("{{ getIc|"))).to.be.true
		})

		it("is false after a closed expression", () => {
			expect(isInsideDynamicValue(contextAt("{{ done }} tra|iling"))).to.be.false
		})

		it("tracks the nearest pair among multiple expressions", () => {
			expect(isInsideDynamicValue(contextAt("{{ a }} static {{ b| }}"))).to.be.true
			expect(isInsideDynamicValue(contextAt("{{ a }} stat|ic {{ b }}"))).to.be.false
		})

		it("works across lines", () => {
			expect(isInsideDynamicValue(contextAt("{\n\ttitle: {{ pageTit|le }}\n}"))).to.be.true
		})
	})

	describe("isInsideFunctionExpression", () => {
		it("is false in static values", () => {
			expect(isInsideFunctionExpression(contextAt('{ icon: "sta|r" }'))).to.be.false
			expect(isInsideFunctionExpression(contextAt("[1, 2, |]"))).to.be.false
		})

		it("is true inside a complete arrow function", () => {
			expect(isInsideFunctionExpression(contextAt("{ formatter: (row) => row.stat|us }"))).to.be.true
		})

		it("is true inside an incomplete arrow function being typed", () => {
			expect(isInsideFunctionExpression(contextAt("{ formatter: (row) => getIc| }"))).to.be.true
		})

		it("is true inside an unclosed function body", () => {
			expect(isInsideFunctionExpression(contextAt("{ formatter: function (value) { return va| "))).to.be.true
		})

		it("is true inside a function nested in an array prop", () => {
			expect(isInsideFunctionExpression(contextAt('[{ label: "Status", formatter: (row) => get| }]'))).to.be.true
		})

		it("is false outside the function in the same document", () => {
			expect(isInsideFunctionExpression(contextAt('{ formatter: (row) => row.status, icon: "sta|r" }'))).to.be.false
		})
	})

	describe("useDynamicValueCompletions", () => {
		before(() => setActivePinia(pinia))

		const getSources = () => useDynamicValueCompletions()()

		it("no source fires in static text", async () => {
			for (const source of getSources()) {
				expect(await source(contextAt('{ icon: "sta|r" }'))).to.be.null
			}
		})

		it("window source suggests globals inside {{ }}", async () => {
			const [, windowSource] = getSources()
			const result = await windowSource(contextAt("{{ setTime| }}"))
			const labels = result!.options.map((option) => option.label)
			expect(labels).to.include("setTimeout")
		})

		it("studio source suggests route/router inside {{ }}", async () => {
			const [studioSource] = getSources()
			const result = await studioSource(contextAt("{{ rou| }}"))
			const labels = result!.options.map((option) => option.label)
			expect(labels).to.include("route").and.to.include("router")
		})
	})
})
