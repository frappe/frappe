<template>
	<div class="mx-5 my-4 flex h-[41rem] max-w-[1340px] flex-col gap-4">
		<div v-if="config_settings.data" class="overflow-x-none flex w-full justify-between gap-2">
			<Dropdown :options="viewDropdownOptions">
				<template #default="{ open }">
					<Button :label="config_settings.data.label">
						<template #prefix>
							<FeatherIcon
								:name="config_settings.data.icon || 'list'"
								class="h-3.5 text-gray-600"
							/>
						</template>
						<template #suffix>
							<FeatherIcon
								:name="open ? 'chevron-up' : 'chevron-down'"
								class="h-3.5 text-gray-600"
							/>
						</template>
					</Button>
				</template>
			</Dropdown>
			<ListControls
				v-if="listConfig.fields"
				v-model="listConfig"
				:options="listControlOptions"
				@update="updateConfig"
				@fetch="fetchList"
				@reload="renderList"
			/>
		</div>
		<ListView
			v-if="listResource.data?.length"
			:rows="listResource.data"
			rowKey="name"
			:columns="listConfig.columns"
			:options="listOptions"
		>
			<template #cell="{ item, row, column }">
				<ListFormatter
					:item="item"
					:row="row"
					:column="column"
					:titleField="listConfig.titleField"
				/>
			</template>
		</ListView>
		<div v-else class="my-4 flex h-full flex-col items-center justify-center gap-4">
			<span class="text-xl font-semibold">No records found</span>
			<Button variant="solid" size="md" :label="'Create New ' + doctype" />
		</div>
	</div>

	<ListFooter
		class="border-t px-5 py-2"
		v-model="pageLength"
		:options="{
			rowCount: listResource.data?.length,
			totalCount: totalCount,
		}"
		@loadMore="handleLoadMore"
	/>
	<ViewActions
		v-model="showViewActionsModal"
		:listConfig="listConfig"
		:queryFilters="queryFilters"
		:mode="viewModalMode"
	/>
</template>

<script setup>
import { isEqual } from "lodash"
import {
	doctype,
	config_name,
	config_settings,
	isDefaultConfig,
	isDefaultOverriden,
} from "@/stores/view"
import { call, createResource, FeatherIcon, Dropdown, ListFooter } from "frappe-ui"
import { ref, computed, watch } from "vue"
import { useRoute, useRouter } from "vue-router"

import { ListView } from "frappe-ui"
import ListControls from "@/components/List/ListControls.vue"
import ListFormatter from "@/components/List/ListFormatter.vue"
import ViewActions from "@/components/ViewActions.vue"
import { doctypesBySlug } from "@/data/permissions"

const route = useRoute()
const router = useRouter()

const doctypeSavedViews = ref([])

const viewDropdownOptions = computed(() => {
	let options = []

	if (isDefaultConfig.value)
		configUpdated.value &&
			options.push({
				group: "View Actions",
				items: [
					{
						label: "Save As",
						icon: "plus",
						onClick: () => {
							viewModalMode.value = "Save View As"
							showViewActionsModal.value = true
						},
					},
				],
			})
	else {
		configUpdated.value &&
			options.push({
				group: "View Actions",
				items: [
					{
						label: "Save Changes",
						icon: "save",
						onClick: () => {
							updateView()
						},
					},
				],
			})

		options.push({
			group: "View Actions",
			items: [
				{
					label: "Rename",
					icon: "edit-3",
					onClick: () => {
						viewModalMode.value = "Save"
						showViewActionsModal.value = true
					},
				},
				{
					label: "Delete",
					icon: "trash",
					onClick: () => {
						viewModalMode.value = "Delete"
						showViewActionsModal.value = true
					},
				},
			],
		})
	}

	options.push({
		group: "Default Views",
		items: [
			{
				label: "List View",
				icon: "list",
				onClick: async () => {
					await router.replace({ query: {} })
				},
			},
			{
				label: "Report View",
				icon: "table",
			},
			{
				label: "Kanban View",
				icon: "grid",
			},
			{
				label: "Dashboard View",
				icon: "pie-chart",
			},
		],
	})
	doctypeSavedViews.value.length &&
		options.push({
			group: "Saved Views",
			items: doctypeSavedViews.value.map((view) => {
				return {
					label: view.label,
					icon: view.icon || "list",
					onClick: async () => {
						await router.replace({ query: { view: view.name } })
					},
				}
			}),
		})
	doctypeSavedViews.value.length > 5 &&
		options.push({
			group: "More Views",
			hideLabel: true,
			items: [
				{
					label: "More Views",
					onClick: () => {},
				},
			],
		})
	return options
})

const listControlOptions = {
	showColumnSettings: true,
	showFilters: true,
	showSortSelector: true,
}

const listOptions = {
	showTooltip: false,
	selectable: true,
	resizeColumn: true,
	rowHeight: 47,
}

const listConfig = ref({})
const oldConfig = ref({})

const configUpdated = computed(() => !isEqual(listConfig.value, oldConfig.value))

// Display list based on default or saved view

const renderList = async () => {
	let view = route.query.view
	await loadConfig(view)
	await addViewFiltersToQueryParams(view)
	await createConfigObj()
	await fetchList()
}

const loadConfig = async (query_config) => {
	isDefaultConfig.value = !query_config
	config_name.value = query_config
	await config_settings.fetch()
	doctypeSavedViews.value = config_settings.data.saved_views
}

const addViewFiltersToQueryParams = async (query_config) => {
	if (query_config == null) return
	let query_params = { view: query_config }
	config_settings.data.filters?.map((f) => {
		let fieldname = f[0]
		if (query_params[fieldname]) query_params[fieldname].push(JSON.stringify([f[1], f[2] + ""]))
		else query_params[fieldname] = [JSON.stringify([f[1], f[2] + ""])]
	})
	await router.push({ query: query_params })
}

const createConfigObj = async () => {
	listConfig.value = {
		columns: config_settings.data.columns,
		fields: config_settings.data.doctype_fields,
		filters: currentFilters.value,
		sort: [config_settings.data.sort_field, config_settings.data.sort_order],
		titleField: config_settings.data.title_field,
	}
	oldConfig.value = JSON.parse(JSON.stringify(listConfig.value))
}

const fetchList = async () => {
	await updateTotalCount()
	await listResource.fetch()
}

const listResource = createResource({
	url: `frappe.desk.doctype.view_config.view_config.get_list`,
	makeParams() {
		return {
			doctype: doctype.value,
			cols: listConfig.value.columns,
			filters: queryFilters.value,
			limit: rowCount.value,
			start: 0,
			order_by: querySort.value,
		}
	},
})

// Maintain current sort and filtering

const currentSort = computed(() => [listConfig.value.sort[0], listConfig.value.sort[1]])

const querySort = computed(() => `${currentSort.value.join(" ")}`)

const getFieldType = (fieldname) => {
	return config_settings.data?.doctype_fields.find((f) => f.value === fieldname).type || ""
}

const getSelectOptions = (fieldname) => {
	return (
		config_settings.data?.doctype_fields.find((f) => f.value === fieldname).options?.split("\n") ||
		[]
	)
}

const getParsedFilter = (key, filter) => {
	let f = JSON.parse(filter)
	return {
		fieldname: key,
		fieldtype: getFieldType(key),
		operator: f[0],
		value: f[1],
		options: getSelectOptions(key),
	}
}

const currentFilters = computed(() => {
	let filters = []
	if (route.query) {
		for (let key in route.query) {
			if (key == "view") continue

			if (typeof route.query[key] == "string") filters.push(getParsedFilter(key, route.query[key]))
			else {
				route.query[key].forEach((v) => {
					filters.push(getParsedFilter(key, v))
				})
			}
		}
	}
	return filters
})

const queryFilters = computed(
	() => currentFilters.value.map((f) => [f.fieldname, f.operator, f.value]) || []
)

// View Actions

const cancelChanges = async () => {
	router.push({ query: { view: route.query.view } })
	await loadConfig(route.query.view)
	await listResource.fetch()
}

const updateView = async () => {
	call("frappe.desk.doctype.view_config.view_config.update_config", {
		config_name: config_name.value,
		config: listConfig.value,
		filters: queryFilters.value,
	}).then(() => {
		oldConfig.value = JSON.parse(JSON.stringify(listConfig.value))
	})
}

watch(
	() => (route.params.doctype, route.query.view),
	async () => {
		doctype.value = doctypesBySlug[route.params.doctype]?.name
		await renderList(doctype.value, route.query.view)
	},
	{ immediate: true }
)

const showViewActionsModal = ref(false)
const viewModalMode = ref("")

const pageLength = ref(20)
const rowCount = ref(20)
const totalCount = ref(0)

const updateTotalCount = async () => {
	totalCount.value = await call("frappe.client.get_count", {
		doctype: doctype.value,
		filters: queryFilters.value,
	})
}

const handleLoadMore = async () => {
	rowCount.value += pageLength.value
	await fetchList()
}

watch(
	() => pageLength.value,
	async () => {
		rowCount.value = pageLength.value
		await fetchList()
	}
)

const updateConfig = async () => {
	if (isDefaultConfig.value) {
		await updateDefaultConfig()
		oldConfig.value = JSON.parse(JSON.stringify(listConfig.value))
	}
	await fetchList()
}

const updateDefaultConfig = async () => {
	await call("frappe.desk.doctype.view_config.view_config.update_config", {
		doctype: doctype.value,
		config: listConfig.value,
		config_name: config_name.value,
	})
}
</script>
