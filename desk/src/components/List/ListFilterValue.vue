<template>
	<Link
		v-if="fieldtype == 'Link'"
		:doctype="options[0]"
		:value="value"
		:class="'form-control'"
		@change="(val) => (value = val)"
	/>
	<DateRangePicker
		v-else-if="dateTypes.includes(fieldtype) && operator == 'between'"
		:value="value"
		@change="(range) => (value = range)"
	/>
	<DatePicker v-else-if="fieldtype == 'Date'" :value="value" @change="(date) => (value = date)" />
	<DatetimePicker
		v-else-if="fieldtype == 'Datetime'"
		:value="value"
		@change="(date) => (value = date)"
	/>
	<FormControl
		v-else-if="['is', 'timespan'].includes(operator)"
		type="select"
		:options="optionsList[operator]"
		v-model="value"
	/>
	<FormControl
		v-else-if="['Check', 'Select'].includes(fieldtype)"
		type="select"
		:options="optionsList[fieldtype]"
		v-model="value"
	/>
	<FormControl v-else-if="numberTypes.includes(fieldtype)" type="number" v-model="value" />
	<FormControl v-else type="text" v-model="value" />
</template>

<script setup>
import { ref, watch } from "vue"
import { FormControl } from "frappe-ui"

import DatePicker from "@/components/controls/DatePicker.vue"
import DatetimePicker from "@/components/controls/DatetimePicker.vue"
import DateRangePicker from "@/components/controls/DateRangePicker.vue"
import Link from "@/components/controls/Link.vue"

const props = defineProps({
	fieldtype: {
		type: String,
		required: true,
	},
	operator: {
		type: String,
		required: true,
	},
	value: {
		type: String,
		required: true,
	},
	options: {
		type: [Array],
		required: true,
	},
})

const value = ref(props.value)

const emit = defineEmits(["update"])

watch(value, (value) => {
	emit("update", value)
})

const timespanOptionsList = [
	{
		label: "Last Week",
		value: "last week",
	},
	{
		label: "Last Month",
		value: "last month",
	},
	{
		label: "Last Quarter",
		value: "last quarter",
	},
	{
		label: "Last 6 Months",
		value: "last 6 months",
	},
	{
		label: "Last Year",
		value: "last year",
	},
	{
		label: "Yesterday",
		value: "yesterday",
	},
	{
		label: "Today",
		value: "today",
	},
	{
		label: "Tomorrow",
		value: "tomorrow",
	},
	{
		label: "This Week",
		value: "this week",
	},
	{
		label: "This Month",
		value: "this month",
	},
	{
		label: "This Quarter",
		value: "this quarter",
	},
	{
		label: "This Year",
		value: "this year",
	},
	{
		label: "Next Week",
		value: "next week",
	},
	{
		label: "Next Month",
		value: "next month",
	},
	{
		label: "Next Quarter",
		value: "next quarter",
	},
	{
		label: "Next 6 Months",
		value: "next 6 months",
	},
	{
		label: "Next Year",
		value: "next year",
	},
]

const checkOptionsList = [
	{
		label: "Yes",
		value: "true",
	},
	{
		label: "No",
		value: "false",
	},
]

const isOptionsList = [
	{
		label: "Set",
		value: "set",
	},
	{
		label: "Not Set",
		value: "not set",
	},
]

const optionsList = {
	timespan: timespanOptionsList,
	is: isOptionsList,
	Check: checkOptionsList,
	Select: props.options,
}

const numberTypes = ["Float", "Int", "Currency", "Percent"]
const dateTypes = ["Date", "Datetime"]
</script>
