<template>
	<div class="flex flex-col gap-3 p-4">
		<CollapsibleSection sectionName="Data Sources">
			<div class="ml-3 flex flex-col gap-1" v-if="!isObjectEmpty(codeStore.resources)">
				<div
					v-for="(resource, resource_name) in codeStore.resources"
					:key="resource_name"
					class="group/item flex flex-row items-center justify-between"
				>
					<ObjectBrowser :object="resource" :name="resource_name" class="-ml-[0.9rem] overflow-hidden" />
					<ItemActions
						class="-mt-1 self-start"
						:menuOptions="getResourceMenu(resource, resource_name)"
						@edit="openResource(resource)"
					/>
				</div>
			</div>

			<EmptyState v-else message="No resources added" />

			<div class="mt-2 flex flex-col" v-if="store.activePage">
				<Button icon-left="plus" @click="showResourceDialog = true">Add Data Source</Button>
				<ResourceDialog
					v-model:showDialog="showResourceDialog"
					:resource="existingResource"
					@addResource="addResource"
					@editResource="editResource"
				/>
			</div>
		</CollapsibleSection>

		<!-- Variables -->
		<CollapsibleSection sectionName="Variables">
			<div class="ml-3 flex flex-col gap-1" v-if="!isObjectEmpty(codeStore.variables)">
				<div
					v-for="(value, variable_name) in codeStore.variables"
					:key="variable_name"
					class="group/item flex flex-row items-center justify-between"
				>
					<ObjectBrowser
						v-if="typeof value === 'object'"
						:object="value"
						:name="variable_name"
						class="-ml-[0.9rem] overflow-hidden"
					/>
					<div v-else class="flex flex-row justify-between font-mono text-xs">
						<div class="font-semibold text-ink-pink-8">{{ variable_name }}</div>
						<template v-if="value !== ''">
							<div class="text-ink-gray-5">&nbsp;=&nbsp;</div>
							<div class="text-ink-violet-8">{{ value }}</div>
						</template>
					</div>
					<ItemActions
						class="-mt-1 self-start"
						:menuOptions="getVariableMenu(variable_name, value)"
						@edit="openVariable(variable_name)"
					/>
				</div>
			</div>

			<EmptyState v-else message="No variables added" />

			<div class="mt-2 flex flex-col" v-if="store.activePage">
				<Button icon-left="plus" @click="showVariableDialog = true">Add Variable</Button>
				<Dialog
					v-model="showVariableDialog"
					:title="variableRef?.name ? 'Edit Variable' : 'Add Variable'"
					@after-leave="
						() =>
							(variableRef = {
								name: '',
								variable_name: '',
								variable_type: 'String',
								initial_value: '',
							})
					"
				>
					<template #default>
						<div class="flex flex-col space-y-4">
							<FormControl
								label="Variable Name"
								v-model="variableRef.variable_name"
								:required="true"
								autocomplete="off"
							/>
							<FormControl
								label="Variable Type"
								type="select"
								:options="['String', 'Number', 'Boolean', 'Object']"
								v-model="variableRef.variable_type"
								:required="true"
								default="String"
								@change="() => setInitialValue()"
							/>
							<Code
								v-if="variableRef.variable_type === 'Object'"
								ref="variableEditor"
								label="Initial Value"
								language="javascript"
								height="250px"
								:showLineNumbers="true"
								v-model="variableRef.initial_value"
								@save="saveVariable(variableRef)"
							/>
							<FormControl
								v-else-if="variableRef.variable_type === 'Number'"
								label="Initial Value"
								type="number"
								:modelValue="variableRef.initial_value"
								@update:modelValue="variableRef.initial_value = Number($event)"
							/>
							<FormControl
								v-else
								label="Initial Value"
								v-model="variableRef.initial_value"
								autocomplete="off"
							/>
						</div>
					</template>
					<template #actions>
						<Button
							variant="solid"
							:label="variableRef.name ? 'Update' : 'Add'"
							@click="saveVariable(variableRef)"
							class="w-full"
						/>
					</template>
				</Dialog>
			</div>
		</CollapsibleSection>
	</div>
</template>

<script setup lang="ts">
import { ref, watch } from "vue"
import { Dialog } from "frappe-ui"
import useStudioStore from "@/stores/studioStore"
import useCodeStore from "@/stores/codeStore"
import CollapsibleSection from "@/components/CollapsibleSection.vue"
import ObjectBrowser from "@/components/ObjectBrowser.vue"
import EmptyState from "@/components/EmptyState.vue"
import ResourceDialog from "@/components/ResourceDialog.vue"
import Code from "@/components/Code.vue"
import ItemActions from "@/components/ItemActions.vue"

import { isObjectEmpty, getAutocompleteValues, getParamsObj, confirm, copyToClipboard } from "@/utils/helpers"
import { studioPageResources } from "@/data/studioResources"
import { studioVariables } from "@/data/studioVariables"
import type { Variable } from "@/types/Studio/StudioPageVariable"
import type { Resource } from "@/types/Studio/StudioResource"
import { toast } from "frappe-ui"

/**
 * Insert resource into DB
 * fetch resources attached to page in store
 * show resources on the data panel
 */

const store = useStudioStore()
const codeStore = useCodeStore()
const showResourceDialog = ref(false)
const existingResource = ref<Resource | null>()

watch(showResourceDialog, (show) => {
	if (!show) {
		existingResource.value = null
	}
})

const addResource = (resource: Resource) => {
	if (!resource.resource_name) {
		toast.error("Data Source Name is required")
		return
	}

	studioPageResources.insert
		.submit({
			...getResourceValues(resource),
			parent: store.activePage?.name,
			parenttype: "Studio Page",
			parentfield: "resources",
		})
		.then(async () => {
			if (store.activePage) {
				await codeStore.setPageResources(store.activePage, true)
			}
			showResourceDialog.value = false
		})
}

const deleteResource = async (resource: Resource, resource_name: string) => {
	const confirmed = await confirm(`Are you sure you want to delete the data source ${resource_name}?`)
	if (confirmed) {
		studioPageResources.delete
			.submit(resource.resource_id)
			.then(async () => {
				if (store.activePage) {
					await codeStore.setPageResources(store.activePage, true)
				}
				toast.success(`Data Source ${resource_name} deleted successfully`)
			})
			.catch(() => {
				toast.error(`Failed to delete data source ${resource_name}`)
			})
	}
}

const editResource = async (resource: Resource) => {
	return studioPageResources.setValue
		.submit(getResourceValues(resource))
		.then(async () => {
			if (store.activePage) {
				await codeStore.setPageResources(store.activePage, true)
			}
			toast.success(`Data Source ${resource.resource_name} updated successfully`)
			showResourceDialog.value = false
		})
		.catch(() => {
			toast.error(`Failed to update data source ${resource.resource_name}`)
		})
}

const getResourceValues = (resource: Resource) => {
	return {
		...resource,
		name: resource.resource_id,
		fields: getAutocompleteValues(resource.fields),
		whitelisted_methods: getAutocompleteValues(resource.whitelisted_methods),
		params: getParamsObj(resource.params),
	}
}

const openResource = async (resource: Resource) => {
	studioPageResources.filters = {
		parent: store.activePage?.name,
		name: resource.resource_id,
	}
	await studioPageResources.reload()

	existingResource.value = studioPageResources.data[0]
	showResourceDialog.value = true
}

const getResourceMenu = (resource: Resource, resource_name: string) => {
	return [
		{
			label: "Delete",
			icon: "lucide-trash",
			theme: "red",
			onClick: () => deleteResource(resource, resource_name),
		},
		{
			label: "Copy Object",
			icon: "lucide-copy",
			onClick: () => {
				copyToClipboard(resource)
			},
		},
	]
}

// variables
const showVariableDialog = ref(false)
const variableEditor = ref()
const variableRef = ref<Variable>({
	name: "",
	variable_name: "",
	variable_type: "String",
	initial_value: "" as string | number | boolean | object | null,
})
const setInitialValue = () => {
	if (variableRef.value.variable_type === "String") {
		variableRef.value.initial_value = ""
	} else if (variableRef.value.variable_type === "Number") {
		variableRef.value.initial_value = 0
	} else if (variableRef.value.variable_type === "Boolean") {
		variableRef.value.initial_value = false
	} else if (variableRef.value.variable_type === "Object") {
		variableRef.value.initial_value = {}
	}
}

const getInitialValue = (variable: Variable) => {
	if (variable.variable_type === "Object" && typeof variable.initial_value !== "string") {
		try {
			return JSON.stringify(variable.initial_value)
		} catch (error) {
			toast.error("Invalid Object")
			throw new Error("Invalid Object")
		}
	} else if (variable.variable_type === "String" && !variable.initial_value) {
		return JSON.stringify("")
	} else if (variable.variable_type === "Boolean" && typeof variable.initial_value === "string") {
		// return string as is - to avoid saving false as "false" in the backend field
		return variable.initial_value
	}
	return JSON.stringify(variable.initial_value)
}

const addVariable = (variable: Variable) => {
	const initial_value = getInitialValue(variable)
	studioVariables.insert.submit(
		{
			variable_name: variable.variable_name,
			variable_type: variable.variable_type,
			initial_value: initial_value,
			parent: store.activePage?.name,
			parenttype: "Studio Page",
			parentfield: "variables",
		},
		{
			async onSuccess() {
				if (store.activePage) {
					await codeStore.setPageVariables(store.activePage)
				}
				showVariableDialog.value = false
			},
			onError(error: any) {
				toast.error("Failed to add variable", {
					description: error.messages.join(", "),
				})
			},
		},
	)
}

const editVariable = (variable: Variable) => {
	const initial_value = getInitialValue(variable)
	studioVariables.setValue
		.submit({
			name: variable.name,
			variable_name: variable.variable_name,
			variable_type: variable.variable_type,
			initial_value: initial_value,
		})
		.then(async () => {
			if (store.activePage) {
				await codeStore.setPageVariables(store.activePage)
			}
			showVariableDialog.value = false
		})
}

const deleteVariable = async (variable: Variable) => {
	const confirmed = await confirm(`Are you sure you want to delete the variable ${variable.variable_name}?`)
	if (confirmed) {
		studioVariables.delete
			.submit(variable.name)
			.then(async () => {
				if (store.activePage) {
					await codeStore.setPageVariables(store.activePage)
				}
				toast.success(`Variable ${variable.variable_name} deleted successfully`)
			})
			.catch(() => {
				toast.error(`Failed to delete variable ${variable.variable_name}`)
			})
	}
}

const openVariable = async (variable_name: string) => {
	const variableConfig = store.variableConfigs[variable_name]
	variableRef.value = { ...variableConfig }
	showVariableDialog.value = true
}

const getVariableMenu = (variable_name: string, value: any) => {
	return [
		{
			label: "Delete",
			icon: "lucide-trash",
			theme: "red",
			onClick: () => {
				const variableConfig = store.variableConfigs[variable_name]
				deleteVariable(variableConfig)
			},
		},
		{
			label: "Copy Name",
			icon: "lucide-copy",
			onClick: () => {
				copyToClipboard(variable_name)
			},
		},
		{
			label: "Copy Value",
			icon: "lucide-copy",
			onClick: () => {
				copyToClipboard(value)
			},
		},
	]
}

const validateVariable = (variable: Variable) => {
	if (variable.variable_type === "Object") {
		variableEditor.value?.emitEditorValue()
		if (variableEditor.value?.errorMessage) {
			return false
		}
	}
	return true
}

const saveVariable = (variable: Variable) => {
	const validated = validateVariable(variable)
	if (!validated) return
	if (variable.name) {
		editVariable(variable)
	} else {
		addVariable(variable)
	}
}
</script>
