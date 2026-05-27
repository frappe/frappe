<template>
	<div class="flex h-full min-h-full flex-col bg-surface-white">
		<div class="flex items-center justify-between border-b border-outline-gray-1 px-3 py-2.5">
			<div class="text-[11px] leading-4 text-ink-gray-5">Session persists for this page</div>
			<button
				v-if="messages.length"
				class="text-xs text-ink-gray-4 hover:text-ink-gray-9"
				@click="clearSession"
			>
				Clear
			</button>
		</div>

		<div ref="messagesEl" class="no-scrollbar flex-1 space-y-4 overflow-y-auto px-4 py-4">
			<div
				v-if="!messages.length"
				class="flex h-full flex-col items-center justify-center gap-2 pb-8 text-center"
			>
				<FeatherIcon name="cpu" class="h-8 w-8 text-ink-gray-3" />
				<p class="text-xs text-ink-gray-4">Chat to create or edit page</p>
			</div>

			<template v-for="msg in messages" :key="msg.id">
				<div v-if="msg.role === 'user'" class="flex flex-col items-end">
					<div class="w-fit max-w-[88%] rounded-md border px-3 py-2 text-sm text-ink-gray-8">
						<div class="whitespace-pre-wrap break-words">{{ msg.content }}</div>
					</div>
				</div>
				<div v-else class="flex flex-col items-start">
					<div class="w-fit max-w-full text-sm text-ink-gray-8">
						<div class="whitespace-pre-wrap break-words">{{ msg.content }}</div>
					</div>
				</div>
			</template>

			<p v-if="loading" class="text-xs italic text-ink-gray-5">
				{{ statusMessage || "Generating…" }}
			</p>
		</div>

		<div class="border-t border-outline-gray-1 p-4">
			<ErrorMessage v-if="error" :message="error" class="mb-2" />

			<div class="relative">
				<textarea
					v-model="prompt"
					rows="4"
					class="w-full resize-none rounded border border-[--surface-gray-2] bg-surface-gray-2 px-2 py-1.5 text-sm text-ink-gray-8 placeholder-ink-gray-4 transition-colors hover:border-[--outline-gray-modals] hover:bg-surface-gray-3 focus:border-outline-gray-4 focus:bg-surface-white focus:shadow-sm focus:ring-0 focus-visible:ring-2 focus-visible:ring-outline-gray-3 disabled:cursor-not-allowed disabled:bg-surface-gray-1 disabled:text-ink-gray-5"
					placeholder="Ask to create or edit this page..."
					:disabled="loading"
					@keydown.meta.enter="generate"
					@keydown.ctrl.enter="generate"
				/>
			</div>

			<div class="mt-2 flex items-center justify-between gap-2">
				<Popover placement="top-start" :offset="6">
					<template #target="{ togglePopover }">
						<button
							class="flex h-7 max-w-[9rem] items-center gap-1.5 rounded px-1.5 text-ink-gray-5 transition-colors hover:bg-surface-gray-2 hover:text-ink-gray-8"
							@click="togglePopover"
						>
							<FeatherIcon name="cpu" class="h-3.5 w-3.5 shrink-0" />
							<span class="truncate text-xs">{{ modelLabel }}</span>
						</button>
					</template>
					<template #body="{ close }">
						<div class="min-w-40 rounded-lg border border-outline-gray-2 bg-surface-white py-1 shadow-lg">
							<button
								v-for="option in modelOptions"
								:key="option.value"
								class="flex w-full items-center px-3 py-1.5 text-left text-sm text-ink-gray-7 hover:bg-surface-gray-2"
								:class="{ 'font-medium text-ink-gray-9': option.value === selectedModel }"
								@click="
									() => {
										selectedModel = option.value
										close()
									}
								"
							>
								{{ option.label }}
							</button>
						</div>
					</template>
				</Popover>

				<Button
					variant="solid"
					label="Generate"
					icon="arrow-up"
					:loading="loading"
					:disabled="!prompt.trim()"
					@click="generate"
				/>
			</div>
		</div>
	</div>
</template>

<script lang="ts" setup>
import { ref, computed, inject, watch, nextTick } from "vue"
import { ErrorMessage, Button, FeatherIcon, call, createResource, Popover } from "frappe-ui"
import { toast } from "vue-sonner"
import useStudioStore from "@/stores/studioStore"
import useCanvasStore from "@/stores/canvasStore"
import { getBlockInstance } from "@/utils/serializer"
import { tryParseYamlBlock } from "@/utils/blockCodec"
import type Block from "@/utils/block"

const store = useStudioStore()
const canvasStore = useCanvasStore()
const socket = inject<any>("socket")

const prompt = ref("")
const loading = ref(false)
const error = ref("")
const statusMessage = ref("")
const selectedModel = ref("")
const streamBuffer = ref("")
const messages = ref<any[]>([])
const messagesEl = ref<HTMLElement | null>(null)

const pageId = computed(() => store.activePage?.name ?? "")

const aiModels = createResource({
	url: "studio.ai.models.get_ai_models",
	auto: true,
	onSuccess(data: any[]) {
		if (data?.length && !selectedModel.value) {
			selectedModel.value = data[0].id
		}
	},
})

const modelOptions = computed(() => (aiModels.data ?? []).map((m: any) => ({ label: m.label, value: m.id })))

const modelLabel = computed(() => {
	const selected = modelOptions.value.find((m: any) => m.value === selectedModel.value)
	return selected ? selected.label : "Model"
})

const sessionResource = createResource({
	url: "studio.ai.page_generator.get_ai_session",
	onSuccess(data: any) {
		messages.value = data.messages ?? []
		if (data.selected_model && !selectedModel.value) {
			selectedModel.value = data.selected_model
		}
		scrollToBottom()
	},
})

function scrollToBottom() {
	nextTick(() => {
		if (messagesEl.value) {
			messagesEl.value.scrollIntoView({ block: "end", behavior: "smooth" })
		}
	})
}

function reloadSession() {
	if (pageId.value) {
		sessionResource.submit({ page_id: pageId.value })
	}
}

function onProgress(data: any) {
	statusMessage.value = data.message || "Generating…"
}

function onStream(data: any) {
	streamBuffer.value += data.chunk || ""
	const block = tryParseYamlBlock(streamBuffer.value)
	if (block) {
		const rootBlock = getBlockInstance(block as any)
		canvasStore.activeCanvas?.setRootBlock(rootBlock, false)
		store.pageBlocks = [rootBlock]
	}
}

async function onComplete(data: any) {
	loading.value = false
	statusMessage.value = ""
	streamBuffer.value = ""

	const block: Block = data.block
	if (!block) {
		error.value = "No block was generated. Try a more descriptive prompt."
		return
	}

	const rootBlock = getBlockInstance(block)
	canvasStore.activeCanvas?.setRootBlock(rootBlock, false)
	store.pageBlocks = [rootBlock]

	await store.savePage()
	toast.success("Page generated successfully")
	prompt.value = ""
	reloadSession()
}

function onError(data: any) {
	loading.value = false
	statusMessage.value = ""
	streamBuffer.value = ""
	error.value = data.message || "Generation failed. Please check your Studio Settings and try again."
}

function setupListeners() {
	if (!socket || !pageId.value) return
	socket.on(`ai_generation_progress_${pageId.value}`, onProgress)
	socket.on(`ai_generation_stream_${pageId.value}`, onStream)
	socket.on(`ai_generation_complete_${pageId.value}`, onComplete)
	socket.on(`ai_generation_error_${pageId.value}`, onError)
}

function detachListeners() {
	if (!socket || !pageId.value) return
	socket.off(`ai_generation_progress_${pageId.value}`, onProgress)
	socket.off(`ai_generation_stream_${pageId.value}`, onStream)
	socket.off(`ai_generation_complete_${pageId.value}`, onComplete)
	socket.off(`ai_generation_error_${pageId.value}`, onError)
}

watch(
	() => pageId.value,
	(newId, oldId) => {
		if (oldId) detachListeners()
		if (newId) {
			setupListeners()
			sessionResource.submit({ page_id: newId })
		}
	},
	{ immediate: true },
)

async function generate() {
	if (!prompt.value.trim()) return
	loading.value = true
	error.value = ""
	statusMessage.value = ""

	messages.value = [...messages.value, { id: Date.now(), role: "user", content: prompt.value }]
	scrollToBottom()

	try {
		await call("studio.ai.page_generator.generate_page_from_prompt", {
			prompt: prompt.value,
			model: selectedModel.value,
			page_id: pageId.value,
		})
	} catch (e: any) {
		loading.value = false
		statusMessage.value = ""
		error.value = e?.message || "Failed to start generation. Please try again."
	}
}

async function clearSession() {
	await call("studio.ai.page_generator.clear_ai_session", { page_id: pageId.value })
	messages.value = []
}
</script>
