<template>
	<CollapsibleSection sectionName="Client Scripts">
		<div class="flex flex-col gap-1">
			<div
				v-if="scripts.length"
				v-for="script in scripts"
				:key="script.name"
				class="group/item flex flex-row items-center justify-between"
			>
				<div class="truncate font-mono text-xs font-semibold text-pink-700">
					{{ scriptLabel(script) }}
				</div>
				<ItemActions :menuOptions="getScriptMenu(script)" @edit="openScript(script)" />
			</div>
			<EmptyState v-else message="No client scripts added" />
		</div>

		<div class="mt-2 flex flex-col">
			<Button icon-left="plus" @click="openNewScript">Add Client Script</Button>
			<Dialog
				v-model="showScriptDialog"
				:title="currentScript.name ? 'Edit Client Script' : 'Add Client Script'"
				size="3xl"
				:dismissible="false"
			>
				<template #default>
					<div class="flex flex-col space-y-3">
						<FormControl type="text" label="Name" variant="outline" v-model="currentScript.script_name" />
						<Code
							label="Script"
							:isFormInput="true"
							language="javascript"
							height="400px"
							maxHeight="400px"
							v-model="currentScript.script"
							:emitOnChange="true"
							:completions="getCompletions"
							@save="saveScript"
						/>
						<FormDescription
							description="Declare functions to reuse across this page's events and bindings. They can read the page's variables and resources directly, e.g. function parseRows() { return contacts.data }"
						/>
					</div>
				</template>
				<template #actions>
					<Button
						variant="solid"
						:label="currentScript.name ? 'Update' : 'Add'"
						@click="saveScript"
						class="w-full"
					/>
				</template>
			</Dialog>
		</div>
	</CollapsibleSection>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue"
import { createListResource, Dialog, FormControl, toast } from "frappe-ui"
import EmptyState from "@/components/EmptyState.vue"
import CollapsibleSection from "@/components/CollapsibleSection.vue"
import Code from "@/components/Code.vue"
import ItemActions from "@/components/ItemActions.vue"
import FormDescription from "@/components/FormDescription.vue"
import { confirm } from "@/utils/helpers"
import { getFunctionDeclarationNames } from "@/utils/parseCode"
import { useStudioCompletions } from "@/utils/useStudioCompletions"
import useCodeStore from "@/stores/codeStore"
import type { StudioPage } from "@/types/Studio/StudioPage"
import type { StudioClientScript } from "@/types/Studio/StudioClientScript"

const props = defineProps<{
	page: StudioPage
}>()

const codeStore = useCodeStore()
const getCompletions = useStudioCompletions(true)

// Junction rows linking this page to its client scripts
const pageClientScripts = createListResource({
	doctype: "Studio Page Client Script",
	parent: "Studio Page",
	fields: ["name", "studio_script", "parent"],
	orderBy: "idx asc",
	pageLength: 50,
})

// The reusable client script docs
const clientScripts = createListResource({
	doctype: "Studio Client Script",
	fields: ["name", "script_name", "script"],
	pageLength: 50,
})

type PageScript = StudioClientScript & { junction?: string }

const scripts = computed<PageScript[]>(() => {
	return (pageClientScripts.data || [])
		.map((row: { name: string; studio_script: string }) => {
			const doc = (clientScripts.data || []).find((d: StudioClientScript) => d.name === row.studio_script)
			if (!doc) return null
			return { name: doc.name, script_name: doc.script_name, script: doc.script, junction: row.name }
		})
		.filter(Boolean) as PageScript[]
})

async function reloadScripts() {
	pageClientScripts.filters = { parent: props.page.name }
	await pageClientScripts.reload()
	const names = pageClientScripts.data
		.map((row: { studio_script: string }) => row.studio_script)
		.filter(Boolean)
	if (names.length) {
		clientScripts.filters = { name: ["in", names] }
		await clientScripts.reload()
	}
	// keep the runtime in sync with edits
	await codeStore.setPageClientScripts(props.page)
}

onMounted(reloadScripts)

const scriptLabel = (script: PageScript) => {
	if (script.script_name) return script.script_name
	const fns = getFunctionDeclarationNames(script.script || "")
	return fns.length ? fns.join(", ") : "Untitled script"
}

// Default display name when the user leaves it blank: the first declared function.
const defaultScriptName = (script: string) => {
	return getFunctionDeclarationNames(script)[0] || "Untitled Script"
}

const showScriptDialog = ref(false)
const currentScript = ref<PageScript>({ name: "", script_name: "", script: "" })

const openNewScript = () => {
	currentScript.value = { name: "", script_name: "", script: "function handleEvent() {\n\t\n}" }
	showScriptDialog.value = true
}

const openScript = (script: PageScript) => {
	currentScript.value = { ...script }
	showScriptDialog.value = true
}

const getScriptMenu = (script: PageScript) => {
	return [
		{
			label: "Delete",
			icon: "lucide-trash",
			theme: "red",
			onClick: () => deleteScript(script),
		},
	]
}

const saveScript = async () => {
	if (!currentScript.value.script?.trim()) {
		toast.error("Script cannot be empty")
		return
	}
	try {
		const scriptName =
			currentScript.value.script_name?.trim() || defaultScriptName(currentScript.value.script)
		if (currentScript.value.name) {
			await clientScripts.setValue.submit({
				name: currentScript.value.name,
				script_name: scriptName,
				script: currentScript.value.script,
			})
		} else {
			const doc = await clientScripts.insert.submit({
				script_name: scriptName,
				script: currentScript.value.script,
			})
			await pageClientScripts.insert.submit({
				parent: props.page.name,
				parenttype: "Studio Page",
				parentfield: "client_scripts",
				studio_script: doc.name,
			})
		}
		await reloadScripts()
		showScriptDialog.value = false
	} catch (error: any) {
		toast.error("Failed to save the client script", {
			description: error?.messages?.join(", "),
		})
	}
}

const deleteScript = async (script: PageScript) => {
	const confirmed = await confirm(`Are you sure you want to delete this client script?`)
	if (!confirmed) return
	try {
		if (script.junction) await pageClientScripts.delete.submit(script.junction)
		if (script.name) await clientScripts.delete.submit(script.name)
		await reloadScripts()
		toast.success("Client script deleted successfully")
	} catch {
		toast.error("Failed to delete the client script")
	}
}
</script>
