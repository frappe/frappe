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
import { ref, computed, inject, onMounted, onUnmounted } from "vue"
import { ErrorMessage, Button, Textarea, Select, call, createResource } from "frappe-ui"
import { toast } from "vue-sonner"
import useStudioStore from "@/stores/studioStore"
import useCanvasStore from "@/stores/canvasStore"
import { getBlockInstance } from "@/utils/serializer"
import type Block from "@/utils/block"

const store = useStudioStore()
const canvasStore = useCanvasStore()
const socket = inject<any>("socket")

const prompt = ref("")
const loading = ref(false)
const error = ref("")
const statusMessage = ref("")
const selectedModel = ref("")

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
	url: "studio.ai_models.get_ai_models",
	auto: true,
	onSuccess(data: any[]) {
		if (data?.length && !selectedModel.value) {
			selectedModel.value = data[0].id
		}
	},
})

const modelOptions = computed(() => (aiModels.data ?? []).map((m: any) => ({ label: m.label, value: m.id })))

function onProgress(data: any) {
	console.log("Progress update:", data)
	statusMessage.value = data.message || "Generating…"
}

async function onComplete(data: any) {
	loading.value = false
	statusMessage.value = ""

	const blocks: Block[] = data.blocks ?? []
	if (!blocks.length) {
		error.value = "No blocks were generated. Try a more descriptive prompt."
		return
	}

	if (selectedBlock.value) {
		selectedBlock.value.children = blocks.map((b: Block) => getBlockInstance(b))
	} else {
		const rootBlock = getBlockInstance(blocks[0])
		canvasStore.activeCanvas?.setRootBlock(rootBlock)
		store.pageBlocks = [rootBlock]
	}

	await store.savePage()
	toast.success("Page generated successfully")
	prompt.value = ""
}

function onError(data: any) {
	loading.value = false
	statusMessage.value = ""
	error.value = data.message || "Generation failed. Please check your Studio Settings and try again."
}

function setupListeners() {
	const id = pageId.value
	if (!socket || !id) return
	socket.on(`ai_generation_progress_${id}`, onProgress)
	socket.on(`ai_generation_complete_${id}`, onComplete)
	socket.on(`ai_generation_error_${id}`, onError)
}

function teardownListeners() {
	const id = pageId.value
	if (!socket || !id) return
	socket.off(`ai_generation_progress_${id}`, onProgress)
	socket.off(`ai_generation_complete_${id}`, onComplete)
	socket.off(`ai_generation_error_${id}`, onError)
}

onMounted(setupListeners)
onUnmounted(teardownListeners)

async function generate() {
	if (!prompt.value.trim()) return
	loading.value = true
	error.value = ""
	statusMessage.value = ""

	try {
		await call("studio.ai.generate_page_from_prompt", {
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
