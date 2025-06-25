<template>
	<div class="flex flex-col gap-1.5">
		<span v-if="props.label" class="block text-xs text-gray-600">
			{{ props.label }}
			<span class="text-ink-red-3" v-if="required">*</span>
		</span>
		<Autocomplete
			ref="autocompleteRef"
			size="sm"
			v-model="value"
			:placeholder="placeholder || `Select ${doctype}`"
			:options="options.data"
			@update:query="handleQueryUpdate"
		/>
	</div>
</template>

<script setup lang="ts">
import { createResource, Autocomplete, debounce } from "frappe-ui"
import { ref, computed, watch } from "vue"
import type { SelectOption } from "@/types"

const props = withDefaults(
	defineProps<{
		doctype: string
		label?: string
		placeholder?: string
		modelValue?: string
		filters?: Record<string, string | [string, string]>
		required?: boolean
		showTitleFieldAsOption?: boolean
	}>(),
	{
		label: "",
		filters: () => ({}),
		showFieldTitleAsOption: true,
	},
)

const emit = defineEmits(["update:modelValue"])

const autocompleteRef = ref<InstanceType<typeof Autocomplete>>(null)
const searchText = ref<string>("")

const value = computed({
	get: () => props.modelValue,
	set: (val: SelectOption | string | undefined) => {
		if (typeof val === "string") {
			emit("update:modelValue", val)
		} else {
			emit("update:modelValue", val?.value || "")
		}
	},
})

const options = createResource({
	url: "frappe.desk.search.search_link",
	params: {
		doctype: props.doctype,
		txt: searchText.value,
		filters: props.filters,
	},
	method: "POST",
	transform: (data: SelectOption[]) => {
		return data.map((doc) => {
			return {
				label: props.showTitleFieldAsOption && doc.label ? doc.label : doc.value,
				value: doc.value,
			}
		})
	},
})

const reloadOptions = (searchTextVal: string) => {
	options.update({
		params: {
			txt: searchTextVal,
			doctype: props.doctype,
		},
	})
	options.reload()
}

const handleQueryUpdate = debounce((newQuery: string) => {
	const val = newQuery || ""
	if (searchText.value === val) return
	searchText.value = val
	reloadOptions(val)
}, 300)

watch(
	() => props.doctype,
	() => {
		if (!props.doctype || props.doctype === options.doctype) return
		reloadOptions("")
	},
	{ immediate: true },
)
</script>
