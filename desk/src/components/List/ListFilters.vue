<template>
	<NestedPopover>
		<template #target>
			<Button label="Filter">
				<template #prefix>
					<FeatherIcon name="filter" class="h-3.5" />
				</template>
				<template v-if="filters?.length" #suffix>
					<div
						class="flex h-5 w-5 items-center justify-center rounded bg-gray-900 pt-[1px] text-2xs font-medium text-white"
					>
						{{ filters?.length }}
					</div>
				</template>
			</Button>
		</template>
		<template #body="{ close }">
			<div class="rounded-lg border border-gray-100 bg-white p-4 shadow-xl">
				<div
					v-if="filters?.length"
					v-for="({ fieldname, fieldtype, operator, value, options }, i) in filters"
					class="mb-3 flex items-center gap-2"
				>
					<div class="w-[9rem]">
						<Autocomplete
							:body-classes="'w-[15rem]'"
							:model-value="fieldname"
							:options="allFilterableFields"
							@update:model-value="(option) => updateField(option, i)"
						/>
					</div>
					<div class="w-[7rem]">
						<FormControl
							type="select"
							:model-value="operator"
							:options="getOperators(i)"
							@update:model-value="(option) => updateOperator(option, i)"
						/>
					</div>
					<!-- Added :key to correctly re-render dynamic child component -->
					<div class="w-[10rem]">
						<ListFilterValue
							:fieldtype="fieldtype"
							:operator="operator"
							:value="value"
							:options="options"
							@update="(val) => updateValue(val, i)"
							:key="fieldname"
						/>
					</div>
					<button icon="x" @click="removeFilter(i)">
						<FeatherIcon name="x" class="h-3.5" />
					</button>
				</div>
				<div v-else class="my-3 min-w-[30rem] pl-3 text-sm text-gray-500">No filters added.</div>
				<div class="flex items-center justify-between gap-2">
					<Autocomplete
						:body-classes="'w-[29rem]'"
						:options="allFilterableFields"
						@update:model-value="(option) => addFilter(option)"
					>
						<template #target="{ togglePopover }">
							<Button
								class="!text-gray-600"
								variant="ghost"
								@click="togglePopover()"
								label="Add Filter"
							>
								<template #prefix>
									<FeatherIcon name="plus" class="h-3" />
								</template>
							</Button>
						</template>
					</Autocomplete>
					<Button
						v-if="filters?.length"
						class="ml-auto !text-gray-600"
						variant="ghost"
						label="Clear All"
						@click="clearFilters(close)"
					>
					</Button>
				</div>
			</div>
		</template>
	</NestedPopover>
</template>

<script setup>
import ListFilterValue from "@/components/List/ListFilterValue.vue"
import NestedPopover from "frappe-ui/src/components/ListFilter/NestedPopover.vue"

import { Button, FeatherIcon, Autocomplete, FormControl } from "frappe-ui"
import { getCurrentInstance } from "vue"
import { useRoute, useRouter } from "vue-router"
import { linkTypes, numberTypes, stringTypes, dateTypes } from "@/stores/list_filter"

const props = defineProps({
	allFilterableFields: {
		type: Array,
		default: [],
	},
})

const filters = defineModel()

// Set up operator options for different fieldtypes

const getOperators = (index) => {
	let f = filters.value[index]
	let fieldname = f.fieldname
	let fieldtype = f.fieldtype
	let options = []
	if (stringTypes.includes(fieldtype)) {
		options.push(
			...[
				{ label: "Equals", value: "=" },
				{ label: "Not Equals", value: "!=" },
				{ label: "Like", value: "like" },
				{ label: "Not Like", value: "not like" },
				{ label: "In", value: "in" },
				{ label: "Not In", value: "not in" },
				{ label: "Is", value: "is" },
			]
		)
	}
	if (fieldname === "_assign") {
		// TODO: make equals and not equals work
		options = [
			{ label: "Like", value: "like" },
			{ label: "Not Like", value: "not like" },
			{ label: "Is", value: "is" },
		]
	}
	if (numberTypes.includes(fieldtype)) {
		options.push(
			...[
				{ label: "Equals", value: "=" },
				{ label: "Not Equals", value: "!=" },
				{ label: "Like", value: "like" },
				{ label: "Not Like", value: "not like" },
				{ label: "In", value: "in" },
				{ label: "Not In", value: "not in" },
				{ label: "Is", value: "is" },
				{ label: "<", value: "<" },
				{ label: ">", value: ">" },
				{ label: "<=", value: "<=" },
				{ label: ">=", value: ">=" },
			]
		)
	}
	if (fieldtype == "Select") {
		options.push(
			...[
				{ label: "Equals", value: "=" },
				{ label: "Not Equals", value: "!=" },
				{ label: "In", value: "in" },
				{ label: "Not In", value: "not in" },
				{ label: "Is", value: "is" },
			]
		)
	}
	if (linkTypes.includes(fieldtype)) {
		options.push(
			...[
				{ label: "Equals", value: "=" },
				{ label: "Not Equals", value: "!=" },
				{ label: "Like", value: "like" },
				{ label: "Not Like", value: "not like" },
				{ label: "In", value: "in" },
				{ label: "Not In", value: "not in" },
				{ label: "Is", value: "is" },
			]
		)
	}
	if (fieldtype == "Check") {
		options.push(...[{ label: "Equals", value: "=" }])
	}
	if (["Duration"].includes(fieldtype)) {
		options.push(
			...[
				{ label: "Like", value: "like" },
				{ label: "Not Like", value: "not like" },
				{ label: "In", value: "in" },
				{ label: "Not In", value: "not in" },
				{ label: "Is", value: "is" },
			]
		)
	}
	if (dateTypes.includes(fieldtype)) {
		options.push(
			...[
				{ label: "Is", value: "is" },
				{ label: ">", value: ">" },
				{ label: "<", value: "<" },
				{ label: ">=", value: ">=" },
				{ label: "<=", value: "<=" },
				{ label: "Between", value: "between" },
				{ label: "Timespan", value: "timespan" },
			]
		)
	}
	return options
}

// Filter Operations

const addFilter = (option) => {
	filters.value.push({
		fieldname: option.value,
		fieldtype: getFieldType(option.value),
		operator: "",
		value: "",
		options: getSelectOptions(option.value),
	})
}

const removeFilter = (index) => {
	filters.value.splice(index, 1)
	updateFiltersInQuery()
}

const clearFilters = (close) => {
	filters.value.splice(0, filters.value.length)
	updateFiltersInQuery()
	close
}

// Update filter options on change of filter field

const getFieldType = (fieldname) => {
	return props.allFilterableFields.find((f) => f.value === fieldname).type || ""
}

const getSelectOptions = (fieldname) => {
	return props.allFilterableFields.find((f) => f.value === fieldname).options?.split("\n") || []
}

const updateField = (option, index) => {
	filters.value[index] = {
		fieldname: option.value,
		fieldtype: getFieldType(option.value),
		options: getSelectOptions(option.value),
		operator: "",
		value: "",
	}
}

const updateOperator = (option, index) => {
	filters.value[index] = { ...filters.value[index], operator: option, value: "" }
}

const updateValue = (value, index) => {
	let filter = filters.value[index]
	let val = value.target ? value.target.value : value
	filter.value = val
	updateFiltersInQuery()
}

// Update filters in query params

const route = useRoute()
const router = useRouter()
const instance = getCurrentInstance()

const updateFiltersInQuery = async () => {
	let q = { view: route.query.view }
	filters.value.map((f) => {
		let fieldname = f.fieldname
		let value = JSON.stringify([f.operator, getFilterValue(f)])
		if (q[fieldname]) q[fieldname].push(value)
		else q[fieldname] = [value]
	})
	await router.replace({ query: q })
	instance.parent.emit("fetch")
}

const getFilterValue = (filter) => {
	if (filter.fieldtype == "Check") {
		return filter.value == "true"
	}
	return filter.value
}
</script>
