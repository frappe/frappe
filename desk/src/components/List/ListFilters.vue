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
					<div class="w-36">
						<Autocomplete
							:body-classes="'w-60'"
							:model-value="fieldname"
							:options="filterableFields"
							@update:model-value="(val: FilterFieldOption) => updateField(val, i)"
						/>
					</div>
					<div class="w-28">
						<FormControl
							type="select"
							:model-value="operator"
							:options="getOperators(fieldtype)"
							@update:model-value="(val: ListFilterOperator) => updateOperator(val, i)"
						/>
					</div>
					<div class="w-40">
						<ListFilterValue
							:fieldtype="fieldtype"
							:operator="operator"
							v-model="filters[i].value"
							:options="options"
							@update:model-value="(val: string) => updateValue(val, i)"
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
						:body-classes="'w-[29rem] '"
						:options="filterableFields"
						@update:model-value="(field: FilterFieldOption) => addFilter(field)"
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

<script setup lang="ts">
import { computed, inject } from "vue"
import { useRouter } from "vue-router"

import { Autocomplete, NestedPopover } from "frappe-ui"
import ListFilterValue from "@/components/List/ListFilterValue.vue"

import {
	linkTypes,
	numberTypes,
	stringTypes,
	dateTypes,
	filterOperators,
} from "@/data/constants/filters"
import { configName, isDefaultConfig } from "@/stores/view"
import { getFilterQuery } from "@/utils/list"

import { fetchListFnKey } from "@/types/injectionKeys"
import { FieldTypes } from "@/types/controls"
import {
	RouteQuery,
	ListField,
	ListFilterOperator,
	ListFilter,
	FilterOperatorOption,
} from "@/types/list"

type FilterFieldOption = ListField & { value: string }

const fetchList = inject(fetchListFnKey) as (updateCount: boolean) => Promise<void>

const props = defineProps<{
	allFilterableFields: ListField[]
}>()

const filters = defineModel<ListFilter[]>({ required: true })

const filterableFields = computed<FilterFieldOption[]>(() => {
	return props.allFilterableFields.map((field) => {
		return {
			...field,
			value: field.key,
		}
	})
})

const getOperatorKey = (fieldtype: FieldTypes): string => {
	if (stringTypes.includes(fieldtype)) return "string"
	else if (numberTypes.includes(fieldtype)) return "number"
	else if (linkTypes.includes(fieldtype)) return "link"
	else if (dateTypes.includes(fieldtype)) return "date"
	else return fieldtype.toLowerCase()
}

const getOperators = (fieldtype: FieldTypes): FilterOperatorOption[] =>
	filterOperators[getOperatorKey(fieldtype)] || []

const addFilter = (field: FilterFieldOption) => {
	filters.value.push({
		fieldname: field.value,
		fieldtype: field.type,
		operator: getOperators(field.type)[0].value,
		value: "",
		options: field.options || [],
	})
}

const removeFilter = (index: number) => {
	filters.value.splice(index, 1)
	updateFiltersInQuery()
}

const clearFilters = (close: () => void) => {
	filters.value.splice(0, filters.value.length)
	updateFiltersInQuery()
	close()
}

const updateField = (field: FilterFieldOption, index: number) => {
	const newOperators = getOperators(field.type)
	// if the current operator is available for the new field, keep it
	let operator = newOperators.find((o) => o.value === filters.value[index].operator)
	// else set the first operator available for the new field
	if (!operator) operator = newOperators[0]
	filters.value[index] = {
		fieldname: field.value,
		fieldtype: field.type,
		options: field.options || [],
		operator: operator.value,
		value: "",
	}
}

const updateOperator = (operator: ListFilterOperator, index: number) => {
	filters.value[index] = { ...filters.value[index], operator: operator, value: "" }
}

const updateValue = (value: string, index: number) => {
	let filter = filters.value[index]
	filter.value = value
	updateFiltersInQuery()
}

const router = useRouter()

const updateFiltersInQuery = async () => {
	let queryParams: RouteQuery = {}
	if (!isDefaultConfig.value) queryParams.view = configName.value
	Object.assign(queryParams, getFilterQuery(filters.value))
	await router.replace({ query: queryParams })
	await fetchList(true)
}
</script>
