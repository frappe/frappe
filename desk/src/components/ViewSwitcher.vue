<template>
	<Dropdown v-if="configSettings.data" :options="viewSwitcherOptions">
		<template #default="{ open }">
			<Button :label="isDefaultConfig ? 'List View' : configSettings.data.label">
				<template #prefix>
					<FeatherIcon :name="configSettings.data.icon || 'list'" class="h-3.5 text-gray-600" />
				</template>
				<template #suffix>
					<FeatherIcon :name="open ? 'chevron-up' : 'chevron-down'" class="h-3.5 text-gray-600" />
				</template>
			</Button>
		</template>
	</Dropdown>

	<Dialog class="pb-0" v-model="showDialog" :options="{ size: 'sm' }">
		<template #body>
			<div class="flex flex-col gap-4 p-5">
				<!-- Dialog Title -->
				<div class="flex items-center justify-between">
					<div class="text-md font-semibold text-gray-900">{{ dialogAction }}</div>
					<FeatherIcon name="x" class="h-4 cursor-pointer" @click="showDialog = false" />
				</div>

				<div v-if="dialogAction == 'Save View As'">
					<div class="flex flex-col gap-4">
						<FormControl
							:type="'text'"
							size="md"
							variant="subtle"
							placeholder="View Name"
							v-model="newViewName"
						/>
						<ErrorMessage
							class="ml-1"
							:message="
								createConfigResource.error?.exc_type === 'DuplicateEntryError'
									? `A view with the name <b>${createConfigResource.params.doc.label}</b> already exists.`
									: createConfigResource.error?.messages[0]
							"
						/>
						<Button variant="solid" label="Save" @click="createConfigResource.submit()">
							<template #prefix>
								<FeatherIcon name="save" class="h-3.5" />
							</template>
						</Button>
					</div>
				</div>

				<div v-else-if="dialogAction == 'Save'">
					<div class="flex flex-col gap-4">
						<FormControl
							:type="'text'"
							size="md"
							variant="subtle"
							placeholder="View Name"
							v-model="configSettings.data.label"
						/>
						<Button variant="solid" label="Update" @click="renameView">
							<template #prefix>
								<FeatherIcon name="save" class="h-3.5" />
							</template>
						</Button>
					</div>
				</div>

				<!-- Delete -->
				<div v-else>
					<div class="flex flex-col gap-4">
						<div class="text-base">Are you sure you want to delete this view?</div>
						<Button variant="outline" theme="red" label="Delete" @click="deleteView">
							<template #prefix>
								<FeatherIcon name="trash" class="h-3.5" />
							</template>
						</Button>
					</div>
				</div>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { ref, computed } from "vue"
import { useRouter } from "vue-router"

import { call, createResource, Dropdown, Dialog, ErrorMessage } from "frappe-ui"

import { cloneObject } from "@/utils"
import {
	configName,
	configSettings,
	isDefaultConfig,
	listConfig,
	oldConfig,
	configUpdated,
	doctypeSavedViews,
} from "@/stores/view"

import { Resource } from "@/types/frappeUI"
import { useRouteParamsAsStrings } from "@/composables/router"
import { RouteQuery, ListQueryFilter } from "@/types/list"

type ViewSwitcherItem = {
	label: string
	icon: string
	onClick: () => void
}

type ViewSwitcherOption = {
	group: string
	items: ViewSwitcherItem[]
	hideLabel?: boolean
}

type createConfigParams = {
	params: {
		doc: Record<string, string | boolean>
	}
	error: {
		exc_type: string
		messages: string[]
	}
}

const props = defineProps<{
	queryFilters: ListQueryFilter[]
}>()

const showDialog = ref(false)
const dialogAction = ref("")
const newViewName = ref("")

const routeParams = useRouteParamsAsStrings()
const router = useRouter()

const createConfigResource: Resource & createConfigParams = createResource({
	url: "frappe.client.insert",
	method: "POST",
	makeParams: () => {
		return {
			doc: {
				doctype: "View Config",
				document_type: routeParams.doctype,
				label: newViewName.value,
				columns: JSON.stringify(listConfig.value?.columns),
				filters: JSON.stringify(props.queryFilters),
				sort_field: listConfig.value?.sort[0],
				sort_order: listConfig.value?.sort[1],
				custom: true,
			},
		}
	},
	onSuccess: async (doc: object) => {
		showDialog.value = false
		newViewName.value = ""
		if ("name" in doc && typeof doc.name === "string")
			await router.replace({ query: { view: doc.name } })
	},
})

const deleteView = async () => {
	showDialog.value = false
	await call("frappe.client.delete", { doctype: "View Config", name: configName.value })
	redirectToView()
}

const renameView = async () => {
	showDialog.value = false
	const viewSlug: string = await call("frappe.desk.doctype.view_config.view_config.rename_config", {
		config_name: configName.value,
		new_name: configSettings.data.label,
	})
	redirectToView(viewSlug)
}

const updateView = async () => {
	call("frappe.desk.doctype.view_config.view_config.update_config", {
		config_name: configName.value,
		config: listConfig.value,
		filters: props.queryFilters,
	}).then(() => {
		if (!listConfig.value) return
		oldConfig.value = cloneObject(listConfig.value)
	})
}

const redirectToView = async (viewName?: string) => {
	let queryParams: RouteQuery = {}
	// Redirect to default view if viewName is not provided
	if (viewName) queryParams.view = viewName
	await router.replace({ query: queryParams })
}

const getActions = () => {
	let actions: ViewSwitcherItem[] = []
	if (isDefaultConfig.value) {
		configUpdated.value &&
			actions.push({
				label: "Save As",
				icon: "plus",
				onClick: () => {
					dialogAction.value = "Save View As"
					showDialog.value = true
				},
			})
	} else {
		configUpdated.value &&
			actions.push({
				label: "Save Changes",
				icon: "save",
				onClick: () => updateView(),
			})

		actions.push(
			{
				label: "Rename",
				icon: "edit-3",
				onClick: () => {
					dialogAction.value = "Save"
					showDialog.value = true
				},
			},
			{
				label: "Delete",
				icon: "trash",
				onClick: () => {
					dialogAction.value = "Delete"
					showDialog.value = true
				},
			}
		)
	}
	return actions
}

const getDefaultViews = (): ViewSwitcherItem[] => {
	return [
		{
			label: "List View",
			icon: "list",
			onClick: () => redirectToView(),
		},
		{
			label: "Report View",
			icon: "table",
			onClick: () => {},
		},
		{
			label: "Kanban View",
			icon: "grid",
			onClick: () => {},
		},
		{
			label: "Dashboard View",
			icon: "pie-chart",
			onClick: () => {},
		},
	]
}

const getSavedViews = (): ViewSwitcherItem[] => {
	if (!doctypeSavedViews.value) return []
	return doctypeSavedViews.value
		.filter((view) => view.name != configName.value)
		.map((view) => {
			return {
				label: view.label,
				icon: view.icon || "list",
				onClick: () => redirectToView(view.name),
			}
		})
}

const viewSwitcherOptions = computed(() => {
	const options: ViewSwitcherOption[] = []

	const actions = getActions()
	if (actions.length) {
		options.push({
			group: "View Actions",
			items: actions,
		})
	}

	options.push({
		group: "Default Views",
		items: getDefaultViews(),
	})

	const savedViews = getSavedViews()
	if (savedViews.length) {
		options.push({
			group: "Saved Views",
			items: savedViews,
		})

		if (savedViews.length > 5) {
			options.push({
				group: "More Views",
				items: [
					{
						label: "More Views",
						icon: "arrow-up-right",
						onClick: () => {},
					},
				],
				hideLabel: true,
			})
		}
	}

	return options
})
</script>
