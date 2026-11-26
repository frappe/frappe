import assert from "node:assert/strict"
import test from "node:test"

import { liveLabelText } from "../src/transcript.js"
import { __ } from "../src/translate.js"

test("text is the English as written until the page around the chat has translations", (t) => {
	assert.equal(__("Save"), "Save")
	assert.equal(__("{0} of {1} records", [2, 5]), "2 of 5 records")

	// an app's own translate function may take its arguments another way: it is never called
	globalThis.__ = () => assert.fail("the page's translate function was called")
	globalThis.translatedMessages = {
		"{0} of {1} records": "{1} Datensätze, {0} gezeigt",
		"Light:Font weight": "Dünn",
		Light: "Hell",
		Retrying: "Neuer Versuch",
	}
	t.after(() => {
		delete globalThis.__
		delete globalThis.translatedMessages
		delete globalThis.frappe
	})
	assert.equal(__("{0} of {1} records", [2, 5]), "5 Datensätze, 2 gezeigt")
	assert.equal(__("Light", null, "Font weight"), "Dünn")
	assert.equal(__("Light"), "Hell")
	assert.equal(__("Save"), "Save")
	// a live status is kept in English, where the tool group compares it, and translated where it shows
	assert.equal(liveLabelText("Retrying"), "Neuer Versuch")
	assert.equal(liveLabelText("Reading file a.js"), "Reading file a.js")
	assert.equal(liveLabelText(null), null)

	// some apps name their list the other way
	delete globalThis.translatedMessages
	globalThis.translated_messages = { Save: "Sichern" }
	t.after(() => delete globalThis.translated_messages)
	assert.equal(__("Save"), "Sichern")

	// Desk's own list is read where the page has one
	globalThis.frappe = { _messages: { Save: "Speichern" } }
	assert.equal(__("Save"), "Speichern")
})
