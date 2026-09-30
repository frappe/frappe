<template>
	<!-- Non-exported apps keep their page scripts in the DB. The editor replaces the panel content
	     and opens directly against the icon rail. -->
	<CodeEditorDock
		:open="true"
		railLeft
		:modelValue="script"
		:completions="completions"
		@update:modelValue="onChange"
		@save="saveScript"
	>
		<template #title>
			<span class="truncate text-sm text-ink-gray-8">Page Script</span>
			<span v-if="dirty" class="text-ink-amber-5">•</span>
		</template>
		<template #actions>
			<Popover side="bottom" align="end" :offset="6" bare>
				<template #trigger>
					<Button size="xs" variant="ghost" icon="lucide-circle-help" title="How to write the page script" />
				</template>
				<div class="max-w-sm rounded-4 border border-outline-gray-2 bg-surface-base p-3 shadow-lg">
					<PageScriptHelp />
				</div>
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
const completions = useStudioCompletions(true, true)

const savedScript = computed(() => store.activePage?.script || "")

const script = ref(savedScript.value)
const saving = ref(false)
const scriptError = ref<string | null>(null)
const dirty = computed(() => script.value !== savedScript.value)

// Reset when switching pages.
watch([() => store.activePage?.name, savedScript], () => {
	script.value = savedScript.value
	scriptError.value = null
})

function onChange(value: string) {
	// the editor also emits on blur, so clicking Save must not wipe the error it is about to show
	if (value !== script.value) scriptError.value = null
	script.value = value
}

async function saveScript() {
	// A broken script fails to compile and takes down every binding on the page, so block it.
	const syntaxError = getScriptError(script.value)
	if (syntaxError) {
		const hint = script.value.includes("{{")
			? " Scripts are plain JavaScript — use expressions directly, not {{ }} interpolation."
			: ""
		scriptError.value = `${syntaxError.message}.${hint}`
		return
	}
	saving.value = true
	try {
		await store.updateActivePage("script", script.value)
		// keep the runtime bindings in sync with the saved script
		codeStore.setPageScript(store.activePage!)
		toast.success("Saved the page script")
	} catch (error: any) {
		toast.error("Failed to save the page script", { description: error?.messages?.join(", ") })
	} finally {
		saving.value = false
	}
}
</script>
