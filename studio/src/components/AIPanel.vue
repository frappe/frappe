<template>
	<div class="flex flex-col gap-4 p-4">
		<div class="flex flex-col gap-1">
			<p class="text-sm font-medium text-ink-gray-7">Describe your page</p>
			<p class="text-xs text-ink-gray-5">
				{{ contextHint }}
			</p>
		</div>

		<Textarea
			v-model="prompt"
			:rows="6"
			placeholder="e.g. A user profile page with name, email, bio fields and a save button"
			:disabled="loading"
		/>

		<ErrorMessage v-if="error" :message="error" />

		<Button
			variant="solid"
			label="Generate"
			@click="generate"
			:loading="loading"
			:disabled="!prompt.trim()"
			class="w-full"
		/>
	</div>
</template>

<script lang="ts" setup>
import { ref, computed } from "vue"
import { ErrorMessage, Button, Textarea, call } from "frappe-ui"
import { toast } from "vue-sonner"
import useStudioStore from "@/stores/studioStore"
import useCanvasStore from "@/stores/canvasStore"
import { getBlockInstance } from "@/utils/serializer"

const store = useStudioStore()
const canvasStore = useCanvasStore()

const prompt = ref("")
const loading = ref(false)
const error = ref("")

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

async function generate() {
	if (!prompt.value.trim()) return
	loading.value = true
	error.value = ""

	try {
		const result = await call("studio.ai.generate_page_from_prompt", { prompt: prompt.value })

		const blocks: any[] = JSON.parse(result)
		if (!blocks?.length) {
			error.value = "No blocks were generated. Try a more descriptive prompt."
			return
		}

		if (selectedBlock.value) {
			// Replace children of the selected block
			selectedBlock.value.children = blocks.map((b: any) => getBlockInstance(b))
		} else {
			// Replace the full page
			const rootBlock = getBlockInstance(blocks[0])
			canvasStore.activeCanvas?.setRootBlock(rootBlock)
			store.pageBlocks = [rootBlock]
		}

		await store.savePage()
		toast.success("Page generated successfully")
		prompt.value = ""
	} catch (e: any) {
		error.value = e?.message || "Generation failed. Please check your Studio Settings and try again."
	} finally {
		loading.value = false
	}
}
</script>
