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
							@update:model-value="(val) => updateField(val, i)"
						/>
					</div>
					<div class="w-[7rem]">
						<FormControl
							type="select"
							:model-value="operator"
							:options="getOperators(i)"
							@update:model-value="(val) => updateOperator(val, i)"
						/>
					</div>
					<div class="w-[10rem]">
						<ListFilterValue
							:fieldtype="fieldtype"
							:operator="operator"
							v-model="filters[i].value"
							:options="options"
							@update:model-value="(val) => updateValue(val, operator, i)"
						/>
					</div>
					<button icon="x" @click="removeFilter(i)">
						<FeatherIcon name="x" class="h-3.5" />
					</button>
				</div>

				<div v-else class="my-3 min-w-[30rem] pl-3 text-sm text-gray-500">No filters added.</div>

				<!-- Filter Actions -->
				<div class="flex items-center justify-between gap-2">
					<Autocomplete
						:body-classes="'w-[29rem]'"
						:options="allFilterableFields"
						@update:model-value="(field) => addFilter(field)"
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

import { Autocomplete } from "frappe-ui"
import { getCurrentInstance } from "vue"
import { useRoute, useRouter } from "vue-router"
import {
	linkTypes,
	numberTypes,
	stringTypes,
	dateTypes,
	filterOperators,
} from "@/data/constants/filters"
import { getFilterQuery } from "@/utils/list"

const props = defineProps({
	allFilterableFields: {
		type: Array,
		default: [],
	},
})

const filters = defineModel()

const getOperators = (index) => {
	let f = filters.value[index]
	let fieldtype = f.fieldtype

	if (stringTypes.includes(fieldtype)) {
		return filterOperators["string"]
	} else if (numberTypes.includes(fieldtype)) {
		return filterOperators["number"]
	} else if (linkTypes.includes(fieldtype)) {
		return filterOperators["link"]
	} else if (dateTypes.includes(fieldtype)) {
		return filterOperators["date"]
	} else if (["Select", "Check", "Duration"].includes(fieldtype)) {
		return filterOperators[fieldtype.toLowerCase()]
	}

	return []
}

const addFilter = (field) => {
	filters.value.push({
		fieldname: field.value,
		fieldtype: field.type,
		operator: "",
		value: "",
		options: field.options || [],
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

const updateField = (field, index) => {
	filters.value[index] = {
		fieldname: field.value,
		fieldtype: field.type,
		options: field.options || [],
		operator: "",
		value: "",
	}
}

const updateOperator = (operator, index) => {
	filters.value[index] = { ...filters.value[index], operator: operator, value: "" }
}

const updateValue = (value, operator, index) => {
	let filter = filters.value[index]
	let val = value.target ? value.target.value : value
	if (operator === "between") {
		val = val.split(",").map((v) => v.trim())
	}
	filter.value = val
	updateFiltersInQuery()
}

const route = useRoute()
const router = useRouter()
const instance = getCurrentInstance()

const updateFiltersInQuery = async () => {
	let q = { view: route.query.view }
	Object.assign(q, getFilterQuery(filters.value))
	await router.replace({ query: q })
	instance.parent.emit("fetch", { updateCount: true })
}
</script>
