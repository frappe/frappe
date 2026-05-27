<template>
	<div class="flex flex-col gap-4 p-4">
		<div class="flex flex-col gap-1">
			<p class="text-sm font-medium text-ink-gray-7">Describe your page</p>
			<p class="text-xs text-ink-gray-5">{{ contextHint }}</p>
		</div>

		<Select
			v-if="modelOptions.length"
			v-model="selectedModel"
			:options="modelOptions"
			placeholder="Select a model"
			:disabled="loading"
		/>

		<Textarea
			v-model="prompt"
			:rows="6"
			placeholder="e.g. A user profile page with name, email, bio fields and a save button"
			:disabled="loading"
		/>

		<p v-if="statusMessage" class="text-xs italic text-ink-gray-5">{{ statusMessage }}</p>
		<ErrorMessage v-if="error" :message="error" />

		<Button
			variant="solid"
			label="Generate"
			:loading="loading"
			:disabled="!prompt.trim()"
			class="w-full"
			@click="generate"
		/>
	</div>
</template>

<script lang="ts" setup>
import { ref, computed, inject, watch } from "vue"
import { ErrorMessage, Button, Textarea, Select, call, createResource } from "frappe-ui"
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

const pageId = computed(() => store.activePage?.name ?? "")

const selectedBlock = computed(() => {
	const block = canvasStore.activeCanvas?.selectedBlocks?.[0] ?? null
	if (block?.isRoot()) return null
	return block
})

const contextHint = computed(() =>
	selectedBlock.value
		? `Generating children for "${selectedBlock.value.blockName || selectedBlock.value.componentName}"`
		: "Generating a full page",
)

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
		if (oldId) {
			detachListeners()
		}
		if (newId) {
			setupListeners()
		}
	},
)

async function generate() {
	if (!prompt.value.trim()) return
	loading.value = true
	error.value = ""
	statusMessage.value = ""

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
</script>
