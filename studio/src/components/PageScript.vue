<template>
	<!-- Non-exported apps keep their code in the DB: one script per page and one router script for
	     the app. The editor replaces the panel content and opens directly against the icon rail. -->
	<CodeEditorDock
		:open="true"
		railLeft
		:modelValue="script"
		:completions="isRouter ? null : getCompletions"
		@update:modelValue="onChange"
		@save="saveScript"
	>
		<template #title>
			<TabButtons
				size="xs"
				v-model="target"
				:options="[
					{ label: activePage?.page_title || 'Page', value: 'page' },
					{ label: 'Router', value: 'router' },
				]"
			/>
			<span v-if="dirty" class="text-ink-amber-5">•</span>
		</template>
		<template #actions>
			<Popover side="bottom" align="end" :offset="6" bare>
				<template #trigger>
					<Button
						size="xs"
						variant="ghost"
						icon="lucide-circle-help"
						:title="`How to write ${scriptLabel}s`"
					/>
				</template>
				<div class="max-w-sm rounded-4 border border-outline-gray-2 bg-surface-base p-3 shadow-lg">
					<RouterScriptHelp v-if="isRouter" />
					<PageScriptHelp v-else />
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
import { toast, Button, Popover, ErrorMessage, TabButtons } from "frappe-ui"
import CodeEditorDock from "@/components/CodeEditorDock.vue"
import PageScriptHelp from "@/components/PageScriptHelp.vue"
import RouterScriptHelp from "@/components/RouterScriptHelp.vue"
import { getScriptError } from "@/utils/parseCode"
import { useStudioCompletions } from "@/utils/useStudioCompletions"
import useCodeStore from "@/stores/codeStore"
import useStudioStore from "@/stores/studioStore"

const store = useStudioStore()
const codeStore = useCodeStore()
const getCompletions = useStudioCompletions(true, true)

const activePage = computed(() => store.activePage)
const target = ref<"page" | "router">("page")
const isRouter = computed(() => target.value === "router")
const scriptLabel = computed(() => (isRouter.value ? "router script" : "page script"))
const savedSource = computed(() =>
	isRouter.value ? store.activeApp?.router_script || "" : activePage.value?.script || "",
)

const script = ref(savedSource.value)
const saving = ref(false)
const scriptError = ref<string | null>(null)

const dirty = computed(() => script.value !== savedSource.value)

// Reset when switching pages or targets.
watch([() => activePage.value?.name, savedSource], () => {
	script.value = savedSource.value
	scriptError.value = null
})

function onChange(value: string) {
	// the editor also emits on blur, so clicking Save must not wipe the error it is about to show
	if (value !== script.value) scriptError.value = null
	script.value = value
}

function getSyntaxError() {
	// the router script is one object literal, so it only parses as an expression
	const syntaxError = getScriptError(isRouter.value ? `(${script.value})` : script.value)
	if (!syntaxError) return null
	const hint = script.value.includes("{{")
		? " Scripts are plain JavaScript — use expressions directly, not {{ }} interpolation."
		: ""
	return `${syntaxError.message}.${hint}`
}

async function saveScript() {
	// A broken script fails to compile and takes down every binding on the page, so block it.
	scriptError.value = getSyntaxError()
	if (scriptError.value) return
	saving.value = true
	try {
		if (isRouter.value) {
			await store.updateActiveApp("router_script", script.value)
		} else if (activePage.value) {
			await store.updateActivePage("script", script.value)
			// keep the runtime bindings in sync with the saved script
			codeStore.setPageScript(activePage.value)
		}
		toast.success(`${isRouter.value ? "Router" : "Page"} script saved`)
	} catch (error: any) {
		toast.error(`Failed to save the ${scriptLabel.value}`, { description: error?.messages?.join(", ") })
	} finally {
		saving.value = false
	}
}
</script>
