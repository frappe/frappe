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
				{{ page.page_title }}
				<span v-if="dirty" class="text-ink-amber-3">•</span>
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
					<div class="max-w-sm rounded border border-outline-gray-2 bg-surface-white p-3 shadow-lg">
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
import { call, toast, Button, Popover, ErrorMessage } from "frappe-ui"
import CodeEditorDock from "@/components/CodeEditorDock.vue"
import PageScriptHelp from "@/components/PageScriptHelp.vue"
import { getScriptError } from "@/utils/parseCode"
import { useStudioCompletions } from "@/utils/useStudioCompletions"
import useCodeStore from "@/stores/codeStore"
import useStudioStore from "@/stores/studioStore"
import type { StudioPage } from "@/types/Studio/StudioPage"

const props = defineProps<{
	page: StudioPage
}>()

const store = useStudioStore()
const codeStore = useCodeStore()
const getCompletions = useStudioCompletions(true)

const script = ref(props.page.script || "")
const savedScript = ref(props.page.script || "")
const saving = ref(false)
const scriptError = ref<string | null>(null)

const dirty = computed(() => script.value !== savedScript.value)

// Reset when switching pages.
watch(
	() => props.page.name,
	() => {
		script.value = props.page.script || ""
		savedScript.value = props.page.script || ""
		scriptError.value = null
	},
)

function onChange(value: string) {
	script.value = value
	scriptError.value = null
}

async function saveScript() {
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
		await call("frappe.client.set_value", {
			doctype: "Studio Page",
			name: props.page.name,
			fieldname: "script",
			value: script.value,
		})
		props.page.script = script.value
		savedScript.value = script.value
		// keep the runtime bindings in sync with the saved script
		codeStore.setPageScript(props.page)
		toast.success("Page script saved")
	} catch (error: any) {
		toast.error("Failed to save the page script", { description: error?.messages?.join(", ") })
	} finally {
		saving.value = false
	}
}
</script>
