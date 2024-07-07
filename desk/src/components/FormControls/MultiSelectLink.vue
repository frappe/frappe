<template>
	<Autocomplete
		:placeholder="`Select ${doctype}s`"
		v-model="selectedOptions"
		:options="options.data"
		:multiple="true"
		@update:modelValue="(val: SelectOption[]) => updateSelectedOptions(val)"
	/>
</template>

<script setup lang="ts">
import { SelectOption, SearchLinkOption } from "@/types/controls"
import { createResource, Autocomplete } from "frappe-ui"
import { ref, watch } from "vue"

const props = withDefaults(
	defineProps<{
		doctype: string
		filters?: Record<string, any>
	}>(),
	{
		filters: () => ({}),
	}
)

const modelValue = defineModel("modelValue", {
	type: String,
	default: "",
})

const selectedOptions = ref<SelectOption[] | string[]>()

const updateSelectedOptions = (val: SelectOption[]) => {
	if (!val) return
	modelValue.value = val.map((v) => v.value).join(",")
}

const options = createResource({
	url: "frappe.desk.search.search_link",
	makeParams() {
		return {
			doctype: props.doctype,
			txt: "",
			filters: props.filters,
		}
	},
	transform: (data: SearchLinkOption[]) => {
		return data.map((doc) => {
			return {
				label: doc.value,
				value: doc.value,
			}
		})
	},
})

watch(
	() => props.doctype,
	() => {
		if (!props.doctype || props.doctype === options.doctype) return
		options.fetch()
		if (modelValue.value) {
			selectedOptions.value = modelValue.value.split(",")
		}
	},
	{ immediate: true }
)
</script>
