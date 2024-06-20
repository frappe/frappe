<template>
	<Link v-if="fieldtype == 'Link'" :doctype="options[0]" v-model="modelValue" />
	<DateRangePicker
		v-else-if="dateTypes.includes(fieldtype) && operator == 'between'"
		v-model="modelValue"
	/>
	<DatePicker v-else-if="fieldtype == 'Date'" v-model="modelValue" />
	<DateTimePicker v-else-if="fieldtype == 'Datetime'" v-model="modelValue" />
	<FormControl
		v-else-if="['is', 'timespan'].includes(operator)"
		type="select"
		:options="filterOptions[operator]"
		v-model="modelValue"
	/>
	<FormControl
		v-else-if="['Check', 'Select'].includes(fieldtype)"
		type="select"
		:options="filterOptions[fieldtype.toLowerCase()] || options"
		v-model="modelValue"
	/>
	<FormControl v-else-if="numberTypes.includes(fieldtype)" type="number" v-model="modelValue" />
	<FormControl v-else type="text" v-model="modelValue" />
</template>

<script setup>
import { DatePicker, DateTimePicker, DateRangePicker } from "frappe-ui"
import { numberTypes, dateTypes, filterOptions } from "@/data/constants/filters"

import Link from "@/components/FormControls/Link.vue"

const props = defineProps({
	fieldtype: {
		type: String,
		required: true,
	},
	operator: {
		type: String,
		required: true,
	},
	options: {
		type: Array,
		required: true,
	},
})

const modelValue = defineModel("modelValue", {
	type: String,
	default: "",
})
</script>
