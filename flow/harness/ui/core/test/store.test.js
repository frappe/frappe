import assert from "node:assert/strict"
import test from "node:test"

import { createFlowStore } from "../src/store.js"

globalThis.localStorage = {
	getItem() {
		return null
	},
	setItem() {},
}

test("successful model selection replaces the header context window", async () => {
	const client = {
		async setModel(sessionId, selection) {
			assert.equal(sessionId, "session-1")
			assert.equal(selection.model, "deepseek/deepseek-chat")
			return {
				model: selection.model,
				context_window: 1_000_000,
				supports_images: false,
			}
		},
	}
	const flow = createFlowStore(client)
	flow.state.sessionId = "session-1"
	flow.state.session = {
		model: "codex/gpt-5.6-sol",
		context_window: 272_000,
		supports_images: true,
	}
	flow.state.conversation.model = "codex/gpt-5.6-sol"
	flow.state.conversation.contextWindow = 272_000

	await flow.selectModel("deepseek/deepseek-chat")

	assert.equal(flow.state.conversation.model, "deepseek/deepseek-chat")
	assert.equal(flow.state.conversation.contextWindow, 1_000_000)
	assert.equal(flow.state.session.context_window, 1_000_000)
})

test("session replay restores the selected model's limit after a trailing model change", async () => {
	const client = {
		async session() {
			return {
				session_id: "session-1",
				model: "deepseek/deepseek-chat",
				reasoning_effort: null,
				context_tokens: 5_000,
				context_window: 1_000_000,
				latest_seq: 1,
			}
		},
		async entries() {
			return {
				entries: [{ type: "model_changed", seq: 1, model: "deepseek/deepseek-chat" }],
				latest_seq: 1,
			}
		},
		stream() {
			return {
				close() {},
				async *[Symbol.asyncIterator]() {},
			}
		},
	}
	const flow = createFlowStore(client)

	await flow.openSession("session-1")

	assert.equal(flow.state.conversation.model, "deepseek/deepseek-chat")
	assert.equal(flow.state.conversation.contextWindow, 1_000_000)
	flow.detach()
})
