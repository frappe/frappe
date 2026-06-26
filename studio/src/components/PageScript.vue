<template>
	<!-- Non-exported apps have a single page script, so the editor replaces the panel content and
	     opens directly against the icon rail when the Code tab is active. -->
	<CodeEditorDock
		:open="true"
		railLeft
		:modelValue="script"
		:completions="getCompletions"
		@update:modelValue="onChange"
		@save="saveScript"
	>
		<template #title>
			<span class="lucide-file size-3.5 shrink-0 text-ink-gray-5" />
			<span class="truncate text-sm text-ink-gray-8">
				{{ activePage?.page_title }}
				<span v-if="dirty" class="text-ink-amber-6">•</span>
			</span>
		</template>
		<template #actions>
			<Popover placement="bottom-end" :offset="6">
				<template #target="{ togglePopover }">
					<Button
						size="xs"
						variant="ghost"
						icon="lucide-help-circle"
						title="How to write page scripts"
						@click="togglePopover"
					/>
				</template>
				<template #body>
					<div class="max-w-sm rounded border border-outline-gray-2 bg-surface-base p-3 shadow-lg">
						<PageScriptHelp />
					</div>
				</template>
			</Popover>
			<Button size="xs" variant="solid" :loading="saving" :disabled="!dirty" @click="saveScript">Save</Button>
			<Button
				size="xs"
				variant="ghost"
				icon="lucide-x"
				title="Close editor"
				@click="store.studioLayout.showLeftPanel = false"
			/>
		</template>

		<template #banner>
			<ErrorMessage
				v-if="scriptError"
				class="border-b border-outline-gray-2 px-3 py-2"
				:message="scriptError"
			/>
		</template>
	</CodeEditorDock>
</template>

<script setup lang="ts">
import { ref, computed, watch } from "vue"
import { toast, Button, Popover, ErrorMessage } from "frappe-ui"
import CodeEditorDock from "@/components/CodeEditorDock.vue"
import PageScriptHelp from "@/components/PageScriptHelp.vue"
import { getScriptError } from "@/utils/parseCode"
import { useStudioCompletions } from "@/utils/useStudioCompletions"
import useCodeStore from "@/stores/codeStore"
import useStudioStore from "@/stores/studioStore"

const store = useStudioStore()
const codeStore = useCodeStore()
const getCompletions = useStudioCompletions(true, true)

const activePage = computed(() => store.activePage)

const script = ref(activePage.value?.script || "")
const savedScript = ref(activePage.value?.script || "")
const saving = ref(false)
const scriptError = ref<string | null>(null)

const dirty = computed(() => script.value !== savedScript.value)

// Reset when switching pages.
watch(
	() => activePage.value?.name,
	() => {
		script.value = activePage.value?.script || ""
		savedScript.value = activePage.value?.script || ""
		scriptError.value = null
	},
)

function onChange(value: string) {
	script.value = value
	scriptError.value = null
}

async function saveScript() {
	const page = activePage.value
	if (!page) return
	// A broken script fails to compile and takes down every binding on the page, so block it.
	scriptError.value = null
	const syntaxError = getScriptError(script.value)
	if (syntaxError) {
		const hint = script.value.includes("{{")
			? " Page scripts are plain JavaScript — use expressions directly, not {{ }} interpolation."
			: ""
		scriptError.value = `${syntaxError.message}.${hint}`
		return
	}
	saving.value = true
	try {
		await store.setActivePageScript(script.value)
		savedScript.value = script.value
		// keep the runtime bindings in sync with the saved script
		codeStore.setPageScript(page)
		toast.success("Page script saved")
	} catch (error: any) {
		toast.error("Failed to save the page script", { description: error?.messages?.join(", ") })
	} finally {
		saving.value = false
	}
}
</script>
