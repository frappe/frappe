<template>
	<div class="flex flex-1 flex-col overflow-hidden bg-surface-base">
		<div
			class="flex shrink-0 items-center justify-between border-b border-outline-gray-1 bg-surface-base px-3 py-2.5"
		>
			<div class="text-[11px] leading-4 text-ink-gray-5">Session persists for this page</div>
			<button
				v-if="messages.length"
				class="text-xs text-ink-gray-4 hover:text-ink-gray-9"
				@click="clearSession"
			>
				Clear
			</button>
		</div>

		<div v-if="!isAIEnabled" class="flex flex-1 flex-col items-start gap-3 p-4">
			<p class="text-p-xs text-ink-gray-6">
				Configure an AI API key in Studio Settings to use the AI assistant.
			</p>
			<Button variant="subtle" label="Open Settings" @click="store.showStudioSettingsDialog = true" />
		</div>

		<div v-else ref="messagesEl" class="no-scrollbar flex-1 space-y-4 overflow-y-auto px-4 py-4">
			<div
				v-if="!messages.length"
				class="flex h-full flex-col items-center justify-center gap-2 pb-8 text-center"
			>
				<LucideSparkle class="h-8 w-8 text-ink-gray-3" />
				<p class="text-xs text-ink-gray-4">Chat to create or edit this page</p>
			</div>

			<template v-for="msg in messages" :key="msg.id">
				<div v-if="msg.role === 'user'" class="flex flex-col items-end">
					<div
						class="w-fit max-w-[88%] rounded-md border bg-surface-gray-1 px-3 py-2 text-p-xs text-ink-gray-8"
					>
						<div class="whitespace-pre-wrap break-words">{{ msg.content }}</div>
					</div>
				</div>
				<div v-else class="flex w-full flex-col items-start gap-2">
					<div class="w-fit max-w-full text-p-xs text-ink-gray-8">
						<div class="whitespace-pre-wrap break-words">{{ msg.content }}</div>
					</div>

					<!-- Proposed plan: sections + palette + approve -->
					<div
						v-if="msg.metadata?.status === 'plan_summary'"
						class="flex w-full flex-col gap-2 rounded-md border border-outline-gray-1 bg-surface-gray-1 p-3"
					>
						<ul v-if="msg.metadata.sections?.length" class="flex flex-col gap-1">
							<li v-for="(section, i) in msg.metadata.sections" :key="i" class="text-p-xs text-ink-gray-7">
								• {{ section }}
							</li>
						</ul>
						<div v-if="msg.metadata.palette" class="text-[11px] text-ink-gray-5">
							Palette: {{ msg.metadata.palette }}
						</div>
						<Button
							variant="solid"
							size="sm"
							label="Approve & build"
							:disabled="loading"
							@click="sendPrompt('Yes, that looks good — go ahead and build it.')"
						/>
					</div>

					<!-- Clarification: tappable answer options -->
					<div
						v-else-if="msg.metadata?.status === 'clarification' && msg.metadata.options?.length"
						class="flex flex-wrap gap-1.5"
					>
						<Button
							v-for="(option, i) in msg.metadata.options"
							:key="i"
							variant="outline"
							size="sm"
							:label="option"
							:disabled="loading"
							@click="sendPrompt(option)"
						/>
					</div>
				</div>
			</template>

			<p v-if="loading" class="text-xs text-ink-gray-5">
				{{ statusMessage || "Generating…" }}
			</p>
		</div>

		<div v-if="isAIEnabled" class="shrink-0 border-t border-outline-gray-1 bg-surface-base p-4">
			<ErrorMessage v-if="error" :message="error" class="mb-2" />

			<div v-if="isModifyMode" class="mb-2 flex items-center gap-1.5 rounded py-1">
				<span class="truncate text-xs text-ink-gray-5">Editing:</span>
				<Badge variant="subtle" size="sm">
					{{ selectedBlock?.blockName || selectedBlock?.componentName }}
				</Badge>
			</div>

			<div class="relative">
				<textarea
					v-model="prompt"
					rows="4"
					class="w-full resize-none rounded border border-[--surface-gray-2] bg-surface-gray-2 px-2 py-1.5 text-p-sm text-ink-gray-8 placeholder-ink-gray-4 transition-colors hover:border-[--outline-elevation-2] hover:bg-surface-gray-3 focus:border-outline-gray-4 focus:bg-surface-base focus:shadow-sm focus:ring-0 focus-visible:ring-2 focus-visible:ring-outline-gray-3 disabled:cursor-not-allowed disabled:bg-surface-gray-1 disabled:text-ink-gray-5"
					:placeholder="
						isModifyMode ? 'Describe what to change in this block...' : 'Chat to create or edit this page...'
					"
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
						<div class="min-w-40 rounded-lg border border-outline-gray-2 bg-surface-base py-1 shadow-lg">
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
					:label="isModifyMode ? 'Edit' : 'Generate'"
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
import { ErrorMessage, Button, Badge, FeatherIcon, call, createResource, Popover } from "frappe-ui"
import useStudioStore from "@/stores/studioStore"
import useCanvasStore from "@/stores/canvasStore"
import { AIChatController } from "@/components/AIChatController"
import { getBlockInstance, getBlockString } from "@/utils/serializer"
import type { BlockOptions } from "@/types"
import { studioSettings } from "@/data/studioSettings"
import LucideSparkle from "~icons/lucide/sparkle"

const store = useStudioStore()
const canvasStore = useCanvasStore()
const socket = inject<any>("socket")

const isAIEnabled = computed(() => !!studioSettings.doc?.ai_api_key)

const prompt = ref("")
const loading = ref(false)
const error = ref("")
const statusMessage = ref("")
const selectedModel = ref("")
const messages = ref<any[]>([])
const messagesEl = ref<HTMLElement | null>(null)

const pageId = computed(() => store.activePage?.name ?? "")

const selectedBlock = computed(() => {
	const block = canvasStore.activeCanvas?.selectedBlocks?.[0] ?? null
	if (!block || block.isRoot()) return null
	return block
})

const isModifyMode = computed(() => !!selectedBlock.value)

const aiModels = createResource({
	url: "studio.ai.models.get_ai_models",
	auto: true,
})

const modelOptions = computed(() => (aiModels.data ?? []).map((m: any) => ({ label: m.label, value: m.id })))

const modelLabel = computed(() => {
	const selected = modelOptions.value.find((m: any) => m.value === selectedModel.value)
	return selected ? selected.label : "Model"
})

const sessionResource = createResource({
	url: "studio.ai.api.get_ai_session",
	onSuccess(data: any) {
		messages.value = data.messages ?? []
		if (data.selected_model) {
			selectedModel.value = data.selected_model
		} else if (modelOptions.value.length) {
			selectedModel.value = modelOptions.value[0].value
		}
		scrollToBottom()
	},
})

function scrollToBottom() {
	nextTick(() => {
		if (messagesEl.value) {
			messagesEl.value.scrollTo({
				top: messagesEl.value.scrollHeight,
				behavior: "smooth",
			})
		}
	})
}

function reloadSession() {
	if (pageId.value) {
		sessionResource.submit({ page_id: pageId.value })
	}
}

const controller = new AIChatController({
	socket,
	messages,
	loading,
	statusMessage,
	error,
	pageId: () => pageId.value,
	getCanvas: () => canvasStore.activeCanvas,
	getPageContext: () => {
		const root = store.pageBlocks?.[0] ?? canvasStore.activeCanvas?.getRootBlock()
		return root ? getBlockString(root) : "[]"
	},
	getSelectedBlockIds: () => (selectedBlock.value ? [selectedBlock.value.componentId] : []),
	setRootBlock: (block: BlockOptions) => {
		const rootBlock = getBlockInstance(block)
		store.pageBlocks = [rootBlock]
		canvasStore.activeCanvas?.setRootBlock(rootBlock, false)
	},
	savePage: () => store.savePage(),
	reloadSession,
	scrollToBottom,
})

function setupListeners() {
	if (!socket || !pageId.value) return
	controller.attach(pageId.value)
}

function detachListeners() {
	if (!socket || !pageId.value) return
	controller.detach(pageId.value)
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
	const text = prompt.value.trim()
	prompt.value = ""
	await controller.submit(text, selectedModel.value)
}

// A clarification option or plan approval is just the user's next message.
function sendPrompt(text: string) {
	if (loading.value) return
	controller.submit(text, selectedModel.value)
}

async function clearSession() {
	await call("studio.ai.api.clear_ai_session", { page_id: pageId.value })
	messages.value = []
}
</script>
