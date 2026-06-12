<template>
	<CollapsibleSection sectionName="Page Script">
		<div class="flex flex-col gap-3">
			<Code
				v-if="hasScript"
				:modelValue="page.script"
				language="javascript"
				:readonly="true"
				:showLineNumbers="true"
				height="200px"
				maxHeight="200px"
			/>
			<EmptyState v-else message="No page script added" />
			<Button icon-left="code" @click="openDialog" class="mt-2">
				{{ hasScript ? "Edit Page Script" : "Add Page Script" }}
			</Button>
		</div>
		<Dialog v-model="showDialog" title="Page Script" size="3xl" :dismissible="false">
			<template #default>
				<div class="flex flex-col space-y-3">
					<Code
						:modelValue="script"
						:isFormInput="true"
						language="javascript"
						height="400px"
						maxHeight="400px"
						:emitOnChange="true"
						:completions="getCompletions"
						@update:modelValue="onChange"
						@save="saveScript"
					/>
					<ErrorMessage v-if="scriptError" :message="scriptError" />
					<FormDescription
						description="Write page logic like a Vue <script setup>: reactive state (ref, reactive), computed values, watchers, and functions — all exposed to this page's events and bindings. Read variables, resources and attached modules directly, e.g. const activeContacts = computed(() => contacts.data.filter(c => c.active))"
					/>
				</div>
			</template>
			<template #actions>
				<Button variant="solid" label="Save" @click="saveScript" class="w-full" />
			</template>
		</Dialog>
	</CollapsibleSection>
</template>

<script setup lang="ts">
import { ref, computed, watch } from "vue"
import { call, toast, Dialog } from "frappe-ui"
import CollapsibleSection from "@/components/CollapsibleSection.vue"
import Code from "@/components/Code.vue"
import EmptyState from "@/components/EmptyState.vue"
import FormDescription from "@/components/FormDescription.vue"
import { getScriptError } from "@/utils/parseCode"
import { useStudioCompletions } from "@/utils/useStudioCompletions"
import useCodeStore from "@/stores/codeStore"
import type { StudioPage } from "@/types/Studio/StudioPage"

const props = defineProps<{
	page: StudioPage
}>()

const codeStore = useCodeStore()
const getCompletions = useStudioCompletions(true)

const showDialog = ref(false)
const script = ref(props.page.script || "")
const scriptError = ref<string | null>(null)

const hasScript = computed(() => Boolean(props.page.script?.trim()))

// Reset the editor when switching pages.
watch(
	() => props.page.name,
	() => {
		script.value = props.page.script || ""
		scriptError.value = null
	},
)

function openDialog() {
	script.value = props.page.script || ""
	scriptError.value = null
	showDialog.value = true
}

function onChange(value: string) {
	script.value = value
	scriptError.value = null
}

async function saveScript() {
	// A broken script fails to compile and takes down every binding on the page, so block it.
	const syntaxError = getScriptError(script.value)
	if (syntaxError) {
		const hint = script.value.includes("{{")
			? " Page scripts are plain JavaScript — use expressions directly, not {{ }} interpolation."
			: ""
		scriptError.value = `${syntaxError.message}.${hint}`
		return
	}
	scriptError.value = null
	try {
		await call("frappe.client.set_value", {
			doctype: "Studio Page",
			name: props.page.name,
			fieldname: "script",
			value: script.value,
		})
		props.page.script = script.value
		// keep the runtime bindings in sync with the saved script
		codeStore.setPageScript(props.page)
		toast.success("Page script saved")
		showDialog.value = false
	} catch (error: any) {
		toast.error("Failed to save the page script", {
			description: error?.messages?.join(", "),
		})
	}
}
</script>
