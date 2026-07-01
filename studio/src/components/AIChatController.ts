import { call } from "frappe-ui"
import type { Ref } from "vue"
import { type AIChatHandlers, attachAIChatListeners, detachAIChatListeners } from "@/components/ai/realtime"
import { ToolDispatcher } from "@/components/ai/toolDispatch"
import type { BlockOptions } from "@/types"
import { tryParseJsonBlock } from "@/utils/blockCodec"
import { throttle } from "@/utils/helpers"

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
	setRootBlock: (block: BlockOptions) => void
	savePage: () => void
	reloadSession: () => void
	scrollToBottom: () => void
	reloadPageData: (opts: { resources?: boolean; variables?: boolean }) => void
}

/**
 * Orchestrates one Studio AI agent turn: sends the user prompt to
 * `studio.ai.api.run` and reacts to the `ai_chat_*` realtime events. Block-tree
 * mutation lives in ToolDispatcher; full-page generation streams as `page_json`.
 */
export class AIChatController {
	sessionId = ""
	private readonly dispatcher: ToolDispatcher
	private pendingAssistantId: number | null = null
	private summary = ""
	private pageBuffer = ""
	private readonly renderStreamedPage: () => void

	constructor(private readonly ctx: AIChatContext) {
		this.dispatcher = new ToolDispatcher({ getCanvas: ctx.getCanvas, setRootBlock: ctx.setRootBlock })
		// Re-parsing + rebuilding the whole tree per token pegs the CPU; the final
		// generate_page op re-applies the authoritative document, so a coarse cadence is fine.
		this.renderStreamedPage = throttle(() => {
			const block = tryParseJsonBlock(this.pageBuffer)
			if (block) this.ctx.setRootBlock(block)
		}, 200)
	}

	get handlers(): AIChatHandlers {
		return {
			onProgress: this.onProgress,
			onStream: this.onStream,
			onToolBatch: this.onToolBatch,
			onClarify: this.onClarify,
			onComplete: this.onComplete,
			onError: this.onError,
			onReload: this.onReload,
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
		this.pageBuffer = ""
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
		this.ctx.statusMessage.value = "Cancelling…"
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
		if (data.kind === "page_json") {
			this.pageBuffer += data.chunk
			this.renderStreamedPage()
			return
		}
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
		this.pageBuffer = ""
		this.ctx.reloadSession()
	}

	onError = (data: any) => {
		this.ctx.loading.value = false
		this.ctx.statusMessage.value = ""
		this.ctx.error.value = data.message || "Request failed."
		this.pendingAssistantId = null
		this.summary = ""
		this.pageBuffer = ""
		this.ctx.reloadSession()
	}

	onReload = (data: any) => {
		// A server tool wrote page data (data sources / variables). Re-fetch so the
		// canvas re-evaluates `{{ }}` bindings against the live data.
		this.ctx.reloadPageData({ resources: !!data.resources, variables: !!data.variables })
	}

	onClarify = (data: any) => {
		this.ctx.loading.value = false
		this.ctx.statusMessage.value = ""
		if (data.plan_summary) {
			this.updatePending(data.headline || "Here's my plan", {
				status: "plan_summary",
				headline: data.headline || "",
				data_plan: data.data_plan || [],
				layout_plan: data.layout_plan || [],
				palette: data.palette || "",
			})
		} else {
			this.updatePending(data.question || "Could you clarify?", {
				status: "clarification",
				options: data.options || [],
			})
		}
		this.pendingAssistantId = null
		this.summary = ""
		// Backend persists+commits clarify messages before emitting, so this is race-free.
		this.ctx.reloadSession()
	}

	// --- helpers ----------------------------------------------------------

	private pushMessage(role: "user" | "assistant", content: string): number {
		const id = Date.now() + this.ctx.messages.value.length
		this.ctx.messages.value = [...this.ctx.messages.value, { id, role, content }]
		return id
	}

	private updatePending(content: string, metadata?: Record<string, any>) {
		if (this.pendingAssistantId == null) return
		const index = this.ctx.messages.value.findIndex((m) => m.id === this.pendingAssistantId)
		if (index === -1) return
		const next = [...this.ctx.messages.value]
		next[index] = {
			...next[index],
			content,
			...(metadata ? { metadata: { ...next[index].metadata, ...metadata } } : {}),
		}
		this.ctx.messages.value = next
	}
}
