<template>
	<MultiSelectLink
		v-if="fieldtype == 'Link' && ['in', 'not in'].includes(operator)"
		:doctype="options[0]"
		v-model="modelValue"
	/>
	<Link v-else-if="fieldtype == 'Link'" :doctype="options[0]" v-model="modelValue" />
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

<script setup lang="ts">
import { DatePicker, DateTimePicker, DateRangePicker } from "frappe-ui"
import { numberTypes, dateTypes, filterOptions } from "@/data/constants/filters"

import Link from "@/components/FormControls/Link.vue"
import MultiSelectLink from "@/components/FormControls/MultiSelectLink.vue"

defineProps<{
	fieldtype: string
	operator: string
	options: string[]
}>()

const modelValue = defineModel<string>({ required: true })
</script>
