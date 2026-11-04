<template>
	<!-- A database app keeps its page scripts on the page doc rather than in its file store, so
	     they open in their own dock against the icon rail instead of in the file explorer. -->
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
				@click="store.showPageScriptEditor = false"
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
import { checkAppScript } from "@/runtime/appRuntime"
import { pageScriptCompletions } from "@/utils/completions/pageScriptCompletions"
import { PAGE_SCRIPT_BOILERPLATE } from "@/utils/constants"
import { usePageScope } from "@/stores/codeStore"
import useStudioStore from "@/stores/studioStore"

const store = useStudioStore()
const pageScope = usePageScope()
const completions = pageScriptCompletions

const savedScript = computed(() => store.activePage?.script || "")

// a page authors the module dialect from the first keystroke
const startingScript = () => savedScript.value || PAGE_SCRIPT_BOILERPLATE

const script = ref(startingScript())
const saving = ref(false)
const scriptError = ref<string | null>(null)
const dirty = computed(() => script.value !== savedScript.value)

// Reset when switching pages.
watch([() => store.activePage?.name, savedScript], () => {
	script.value = startingScript()
	scriptError.value = null
})

function onChange(value: string) {
	// the editor also emits on blur, so clicking Save must not wipe the error it is about to show
	if (value !== script.value) scriptError.value = null
	script.value = value
}

async function saveScript() {
	// A broken script fails to compile and takes down every binding on the page, so block it.
	const syntaxError = await checkAppScript(script.value)
	if (syntaxError) {
		const hint = script.value.includes("{{")
			? " Scripts are plain TypeScript — use expressions directly, not {{ }} interpolation."
			: ""
		scriptError.value = `${syntaxError}.${hint}`
		return
	}
	saving.value = true
	try {
		await store.updateActivePage("script", script.value)
		// keep the runtime bindings in sync with the saved script
		pageScope.loadPageScript(store.activePage!)
		toast.success("Saved the page script")
	} catch (error: any) {
		toast.error("Failed to save the page script", { description: error?.messages?.join(", ") })
	} finally {
		saving.value = false
	}
}
</script>
