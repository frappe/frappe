<template>
	<div class="flex flex-col gap-3 p-4">
		<CollapsibleSection sectionName="Data Sources">
			<div class="ml-3 flex flex-col gap-2" v-if="!isObjectEmpty(store.resources)">
				<div
					v-for="(resource, resource_name) in store.resources"
					:key="resource_name"
					class="group/resource flex flex-row justify-between"
				>
					<ObjectBrowser :object="resource" :name="resource_name" class="-ml-[0.9rem] overflow-hidden" />
					<div
						class="invisible -mt-1 ml-auto self-start text-gray-600 group-hover/resource:visible has-[.active-item]:visible"
					>
						<Dropdown :options="getResourceMenu(resource, resource_name)" trigger="click">
							<template v-slot="{ open }">
								<button
									class="flex cursor-pointer items-center rounded-sm p-1 text-gray-700 hover:bg-gray-300"
									:class="open ? 'active-item' : ''"
								>
									<FeatherIcon name="more-horizontal" class="h-3 w-3" />
								</button>
							</template>
						</Dropdown>
					</div>
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
			<div class="ml-3 flex flex-col gap-1" v-if="!isObjectEmpty(store.variables)">
				<div
					v-for="(value, variable_name) in store.variables"
					:key="variable_name"
					class="group/variable flex flex-row justify-between"
				>
					<ObjectBrowser
						v-if="typeof value === 'object'"
						:object="value"
						:name="variable_name"
						class="-ml-[0.9rem] overflow-hidden"
					/>
					<div v-else class="flex flex-row justify-between font-mono text-xs">
						<div class="font-semibold text-pink-700">{{ variable_name }}</div>
						<template v-if="value !== ''">
							<div class="text-gray-600">&nbsp;=&nbsp;</div>
							<div class="text-violet-700">{{ value }}</div>
						</template>
					</div>
					<div
						class="invisible -mt-1 ml-auto self-start text-gray-600 group-hover/variable:visible has-[.active-item]:visible"
					>
						<Dropdown :options="getVariableMenu(variable_name, value)" trigger="click">
							<template v-slot="{ open }">
								<button
									class="flex cursor-pointer items-center rounded-sm p-1 text-gray-700 hover:bg-gray-300"
									:class="open ? 'active-item' : ''"
								>
									<FeatherIcon name="more-horizontal" class="h-3 w-3" />
								</button>
							</template>
						</Dropdown>
					</div>
				</div>
			</div>

			<EmptyState v-else message="No variables added" />

			<div class="mt-2 flex flex-col" v-if="store.activePage">
				<Button icon-left="plus" @click="showVariableDialog = true">Add Variable</Button>
				<Dialog
					v-model="showVariableDialog"
					:options="{
						title: variableRef?.name ? 'Edit Variable' : 'Add Variable',
					}"
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
					<template #body-content>
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
								label="Initial Value"
								language="javascript"
								height="250px"
								:showLineNumbers="true"
								v-model="variableRef.initial_value"
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
							@click="
								() => {
									if (variableRef.name) {
										editVariable(variableRef)
									} else {
										addVariable(variableRef)
									}
								}
							"
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
import CollapsibleSection from "@/components/CollapsibleSection.vue"
import ObjectBrowser from "@/components/ObjectBrowser.vue"
import EmptyState from "@/components/EmptyState.vue"
import ResourceDialog from "@/components/ResourceDialog.vue"
import Code from "@/components/Code.vue"

import { isObjectEmpty, getAutocompleteValues, confirm, copyToClipboard } from "@/utils/helpers"
import { studioResources, studioPageResources } from "@/data/studioResources"
import { studioVariables } from "@/data/studioVariables"
import type { Variable } from "@/types/Studio/StudioPageVariable"
import type { NewResource, Resource } from "@/types/Studio/StudioResource"
import { toast } from "vue-sonner"

/**
 * Insert resource into DB
 * Attach resource to page
 * fetch resources attached to page in store
 * show resources on the data panel
 */

const store = useStudioStore()
const showResourceDialog = ref(false)
const existingResource = ref<Resource | null>()

watch(showResourceDialog, (show) => {
	if (!show) {
		existingResource.value = null
	}
})

const attachResource = async (resource: Resource) => {
	studioPageResources.insert
		.submit({
			studio_resource: resource.name,
			parent: store.activePage?.name,
			parenttype: "Studio Page",
			parentfield: "resources",
		})
		.then(async () => {
			if (store.activePage) {
				await store.setPageResources(store.activePage)
			}
			showResourceDialog.value = false
		})
}

const addResource = (resource: NewResource) => {
	if (resource.source === "Existing Data Source") {
		attachResource(resource as unknown as Resource)
		return
	}
	if (!resource.resource_name) {
		toast.error("Data Source Name is required")
		return
	}

	studioResources.insert.submit(getResourceValues(resource)).then((res: Resource) => {
		studioPageResources.filters = { parent: store.activePage?.name }
		attachResource(res)
	})
}

const deleteResource = async (resource: Resource, resource_name: string) => {
	const confirmed = await confirm(`Are you sure you want to delete the data source ${resource_name}?`)
	if (confirmed) {
		studioPageResources.delete
			.submit(resource.resource_child_table_id)
			.then(async () => {
				try {
					// try deleting the main resource - will fail if linked to other pages
					await studioResources.delete.submit(resource.resource_id)
				} catch (error) {
					console.log(`Failed to delete the main resource doc ${resource.resource_id}: ${error}`)
				}

				if (store.activePage) {
					store.setPageResources(store.activePage)
				}
				toast.success(`Data Source ${resource_name} deleted successfully`)
			})
			.catch(() => {
				toast.error(`Failed to delete data source ${resource_name}`)
			})
	}
}

const editResource = async (resource: Resource) => {
	return studioResources.setValue
		.submit(getResourceValues(resource))
		.then(async () => {
			if (store.activePage) {
				await store.setPageResources(store.activePage)
			}
			toast.success(`Data Source ${resource.resource_name} updated successfully`)
			showResourceDialog.value = false
		})
		.catch(() => {
			toast.error(`Failed to update data source ${resource.resource_name}`)
		})
}

const getResourceValues = (resource: Resource | NewResource) => {
	return {
		...resource,
		name: resource.resource_id,
		fields: getAutocompleteValues(resource.fields),
		whitelisted_methods: getAutocompleteValues(resource.whitelisted_methods),
	}
}

const getResourceMenu = (resource: Resource, resource_name: string) => {
	return [
		{
			label: "Edit",
			icon: "edit",
			onClick: async () => {
				studioPageResources.filters = {
					parent: store.activePage?.name,
					name: resource.resource_child_table_id,
				}
				await studioPageResources.reload()

				existingResource.value = studioPageResources.data[0]
				showResourceDialog.value = true
			},
		},
		{
			label: "Delete",
			icon: "trash",
			onClick: () => deleteResource(resource, resource_name),
		},
		{
			label: "Copy Object",
			icon: "copy",
			onClick: () => {
				copyToClipboard(resource)
			},
		},
	]
}

// variables
const showVariableDialog = ref(false)
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
					await store.setPageVariables(store.activePage)
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
				await store.setPageVariables(store.activePage)
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
					await store.setPageVariables(store.activePage)
				}
				toast.success(`Variable ${variable.variable_name} deleted successfully`)
			})
			.catch(() => {
				toast.error(`Failed to delete variable ${variable.variable_name}`)
			})
	}
}

const getVariableMenu = (variable_name: string, value: any) => {
	const variableConfig = store.variableConfigs[variable_name]
	return [
		{
			label: "Edit",
			icon: "edit",
			onClick: async () => {
				variableRef.value = { ...variableConfig }
				showVariableDialog.value = true
			},
		},
		{
			label: "Delete",
			icon: "trash",
			onClick: () => deleteVariable(variableConfig),
		},
		{
			label: "Copy Name",
			icon: "copy",
			onClick: () => {
				copyToClipboard(variable_name)
			},
		},
		{
			label: "Copy Value",
			icon: "copy",
			onClick: () => {
				copyToClipboard(value)
			},
		},
	]
}
</script>
