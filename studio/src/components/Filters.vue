<template>
	<div class="flex flex-col gap-1.5">
		<FormInputLabel v-if="label">{{ label }}</FormInputLabel>
		<div class="rounded-lg border border-outline-elevation-2 bg-surface-base">
			<div class="min-w-[400px] p-2">
				<div
					v-if="filters.length"
					v-for="(filter, i) in filters"
					:key="i"
					id="filter-list"
					class="mb-3 flex items-center justify-between gap-2"
				>
					<div class="flex flex-1 items-center gap-2">
						<div class="w-13 flex-shrink-0 pl-2 text-end text-base text-ink-gray-5">
							{{ i == 0 ? "Where" : "And" }}
						</div>
						<div id="fieldname" class="!min-w-[120px] flex-1">
							<Combobox :options="fields" v-model="filter.fieldname" placeholder="Filter by..." />
						</div>
						<div id="operator" class="!min-w-[120px] flex-shrink-0">
							<FormControl
								type="select"
								:modelValue="filter.operator"
								@update:modelValue="filter.operator = $event"
								:options="getOperators(filter.field.fieldtype)"
								placeholder="Operator"
							/>
						</div>
						<div id="value" class="flex-1">
							<Link
								v-if="typeLink.includes(filter.field.fieldtype) && ['=', '!='].includes(filter.operator)"
								:doctype="filter.field.options as string"
								:modelValue="filter.value"
								@update:modelValue="filter.value = $event"
								placeholder="Value"
							/>
							<component
								v-else
								:is="getValueSelector(filter.field.fieldtype, filter.field.options)"
								v-model="filter.value"
								placeholder="Value"
								autocomplete="off"
							/>
						</div>
					</div>
					<div class="flex-shrink-0">
						<Button variant="ghost" icon="lucide-x" @click="removeFilter(i)" />
					</div>
				</div>
				<div v-else class="mb-3 flex h-7 items-center px-3 text-sm text-ink-gray-5">
					Empty - Choose a field to filter by
				</div>
				<div class="flex items-center justify-between gap-2">
					<Combobox
						:modelValue="''"
						:options="fields"
						@update:modelValue="(value: string) => addFilter(value)"
						placeholder="Filter by..."
					>
						<template #trigger>
							<Button class="!text-ink-gray-5" variant="ghost" label="Add filter">
								<template #prefix>
									<FeatherIcon name="plus" class="h-4" />
								</template>
							</Button>
						</template>
					</Combobox>
					<Button
						v-if="filters.length"
						class="!text-ink-gray-5"
						variant="ghost"
						label="Clear all filter"
						@click="filters = []"
					/>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { Combobox, FeatherIcon, FormControl } from "frappe-ui"
import { computed, h, ref, watch } from "vue"
import { Link } from "frappe-ui/frappe"

import FormInputLabel from "@/components/FormInputLabel.vue"
import type { DocTypeField, Fieldtype, Filter, Operators } from "@/types"
import { isObjectEmpty } from "@/utils/helpers"
import type { Filters } from "@/types/Studio/StudioResource"

const typeCheck = ["Check"]
const typeLink = ["Link"]
const typeNumber = ["Float", "Int"]
const typeSelect = ["Select"]
const typeString = ["Data", "Long Text", "Small Text", "Text Editor", "Text", "JSON", "Code"]

const emits = defineEmits(["update:modelValue"])

const props = withDefaults(
	defineProps<{
		label?: string
		modelValue?: Filters
		docfields: DocTypeField[]
	}>(),
	{
		label: "",
		modelValue: () => ({}),
		docfields: () => [],
	},
)

const fields = computed(() => {
	return props.docfields
		.filter((field) => {
			return (
				!field.is_virtual &&
				(typeCheck.includes(field.fieldtype) ||
					typeLink.includes(field.fieldtype) ||
					typeNumber.includes(field.fieldtype) ||
					typeSelect.includes(field.fieldtype) ||
					typeString.includes(field.fieldtype))
			)
		})
		.map((field) => {
			return {
				value: field.fieldname,
				...field,
				description: field.fieldtype,
			}
		})
})

const filters = ref<Filter[]>(makeFiltersList(props.modelValue))
watch(filters, (value) => emits("update:modelValue", makeFiltersDict(value)), { deep: true })
watch(
	() => props.modelValue,
	(value) => {
		const newFilters = makeFiltersList(value)
		if (JSON.stringify(filters.value) !== JSON.stringify(newFilters)) {
			filters.value = newFilters
		}
	},
	{ deep: true },
)

function makeFiltersList(filtersDict: Filters) {
	if (!fields.value.length || isObjectEmpty(filtersDict)) return []

	return Object.entries(filtersDict).map(([fieldname, [operator, value]]) => {
		const field = getField(fieldname)
		if (!field) {
			throw new Error(`Field not found: ${fieldname}`)
		}
		return {
			fieldname,
			operator,
			value,
			field,
		}
	})
}

function getField(fieldname: string): DocTypeField | undefined {
	return fields.value.find((f) => f.fieldname === fieldname)
}

function makeFiltersDict(filtersList: Filter[]) {
	if (!filtersList.length) return {}
	return filtersList.reduce((acc: Record<string, any>, filter) => {
		const { fieldname, operator, value } = filter
		acc[fieldname] = [operator, value]
		return acc
	}, {})
}

function getOperators(fieldtype: Fieldtype) {
	let options = []
	if (typeString.includes(fieldtype) || typeLink.includes(fieldtype)) {
		options.push(
			...[
				{ label: "Equals", value: "=" },
				{ label: "Not Equals", value: "!=" },
				{ label: "Like", value: "like" },
				{ label: "Not Like", value: "not like" },
			],
		)
	}
	if (typeNumber.includes(fieldtype)) {
		options.push(
			...[
				{ label: "<", value: "<" },
				{ label: ">", value: ">" },
				{ label: "<=", value: "<=" },
				{ label: ">=", value: ">=" },
				{ label: "Equals", value: "=" },
				{ label: "Not Equals", value: "!=" },
			],
		)
	}
	if (typeSelect.includes(fieldtype)) {
		options.push(
			...[
				{ label: "Equals", value: "=" },
				{ label: "Not Equals", value: "!=" },
			],
		)
	}
	if (typeCheck.includes(fieldtype)) {
		options.push(...[{ label: "Equals", value: "=" }])
	}
	return options
}

function getDefaultOperator(fieldtype: Fieldtype): Operators {
	if (
		typeSelect.includes(fieldtype) ||
		typeLink.includes(fieldtype) ||
		typeCheck.includes(fieldtype) ||
		typeNumber.includes(fieldtype)
	) {
		return "="
	}
	return "like"
}

function getValueSelector(fieldtype: Fieldtype, options: string = "") {
	if (typeSelect.includes(fieldtype) || typeCheck.includes(fieldtype)) {
		const _options = fieldtype == "Check" ? ["Yes", "No"] : getSelectOptions(options)
		return h(FormControl, {
			type: "select",
			options: _options,
		})
	} else {
		return h(FormControl, { type: "text" })
	}
}

function getDefaultValue(field: DocTypeField) {
	if (typeSelect.includes(field.fieldtype)) {
		return getSelectOptions(field.options)[0]
	}
	if (typeCheck.includes(field.fieldtype)) {
		return "Yes"
	}
	return ""
}

function getSelectOptions(options: string = "") {
	return options.split("\n")
}

function addFilter(fieldname: string) {
	const field = getField(fieldname)
	if (!field) return
	const filter = {
		fieldname,
		operator: getDefaultOperator(field.fieldtype),
		value: getDefaultValue(field),
		field,
	}
	filters.value = [...filters.value, filter]
}

function removeFilter(index: number) {
	filters.value = filters.value.filter((_, i) => i !== index)
}
</script>
