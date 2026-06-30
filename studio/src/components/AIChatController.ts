import { call } from "frappe-ui"
import type { Ref } from "vue"
import { type AIChatHandlers, attachAIChatListeners, detachAIChatListeners } from "@/components/ai/realtime"
import { ToolDispatcher } from "@/components/ai/toolDispatch"

/** Everything the controller needs from the panel: the shared chat state it mutates
 * and the canvas/page helpers it drives. Keeps the controller free of Vue component
 * internals so the agent turn lifecycle lives in one testable place. */
export interface AIChatContext {
	socket: any
	messages: Ref<any[]>
	loading: Ref<boolean>
	statusMessage: Ref<string>
	error: Ref<string>
	pageId: () => string
	getCanvas: () => any
	getPageContext: () => string
	getSelectedBlockIds: () => string[]
	savePage: () => void
	reloadSession: () => void
	scrollToBottom: () => void
}

/**
 * Orchestrates one Studio AI agent turn: sends the user prompt to
 * `studio.ai.api.run` and reacts to the `ai_chat_*` realtime events. Block-tree
 * mutation lives in ToolDispatcher.
 */
export class AIChatController {
	sessionId = ""
	private readonly dispatcher: ToolDispatcher
	private pendingAssistantId: number | null = null
	private summary = ""

	constructor(private readonly ctx: AIChatContext) {
		this.dispatcher = new ToolDispatcher(ctx.getCanvas)
	}

	get handlers(): AIChatHandlers {
		return {
			onProgress: this.onProgress,
			onStream: this.onStream,
			onToolBatch: this.onToolBatch,
			onClarify: this.onClarify,
			onComplete: this.onComplete,
			onError: this.onError,
		}
	}

	attach(pageId: string) {
		attachAIChatListeners(this.ctx.socket, pageId, this.handlers)
	}

	detach(pageId: string) {
		detachAIChatListeners(this.ctx.socket, pageId, this.handlers)
	}

	async submit(promptText: string, model: string) {
		this.summary = ""
		this.ctx.error.value = ""
		this.ctx.loading.value = true
		this.ctx.statusMessage.value = ""
		this.pushMessage("user", promptText)
		this.pendingAssistantId = this.pushMessage("assistant", "Thinking…")
		this.ctx.scrollToBottom()
		try {
			const res: any = await call("studio.ai.api.run", {
				prompt: promptText,
				page_id: this.ctx.pageId(),
				page_context: this.ctx.getPageContext(),
				model,
				selected_block_ids: this.ctx.getSelectedBlockIds(),
			})
			if (res?.session_id) this.sessionId = res.session_id
			if (res?.status === "busy") {
				this.onError({ message: res.message || "Another AI request is still processing." })
			}
		} catch (e: any) {
			this.onError({ message: e?.message || "Failed to start. Please try again." })
		}
	}

	cancel = async () => {
		if (!this.sessionId) return
		try {
			await call("studio.ai.api.cancel", { session_id: this.sessionId })
		} catch {
			// Ignore — the user will see the cancelled event when it arrives.
		}
	}

	// --- realtime handlers ------------------------------------------------

	onProgress = (data: any) => {
		this.ctx.loading.value = true
		this.ctx.statusMessage.value = data.message || this.ctx.statusMessage.value
	}

	onStream = (data: any) => {
		if (!data.chunk) return
		this.summary += data.chunk
		this.updatePending(this.summary)
		this.ctx.scrollToBottom()
	}

	onToolBatch = (data: any) => {
		if (!data.operations?.length) return
		this.dispatcher.applyToolBatch(data.operations)
		this.ctx.savePage()
		this.ctx.scrollToBottom()
	}

	onComplete = (data: any) => {
		this.ctx.loading.value = false
		this.ctx.statusMessage.value = ""
		this.updatePending(this.summary || data.message || "Done")
		this.pendingAssistantId = null
		this.summary = ""
		this.ctx.reloadSession()
	}

	onError = (data: any) => {
		this.ctx.loading.value = false
		this.ctx.statusMessage.value = ""
		this.ctx.error.value = data.message || "Request failed."
		this.pendingAssistantId = null
		this.summary = ""
		this.ctx.reloadSession()
	}

	onClarify = (_data: any) => {
		// Terminal tools (ask_clarification / propose_plan) land in a later slice.
	}

	// --- helpers ----------------------------------------------------------

	private pushMessage(role: "user" | "assistant", content: string): number {
		const id = Date.now() + this.ctx.messages.value.length
		this.ctx.messages.value = [...this.ctx.messages.value, { id, role, content }]
		return id
	}

	private updatePending(content: string) {
		if (this.pendingAssistantId == null) return
		const index = this.ctx.messages.value.findIndex((m) => m.id === this.pendingAssistantId)
		if (index === -1) return
		const next = [...this.ctx.messages.value]
		next[index] = { ...next[index], content }
		this.ctx.messages.value = next
	}
}
