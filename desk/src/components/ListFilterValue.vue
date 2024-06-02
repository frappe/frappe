<template>
	<template v-if="['is', 'timespan'].includes(operator)">
		<FormControl type="select" :options="optionsList[operator]" v-model="value" />
	</template>

	<template v-else-if="['Check', 'Select'].includes(fieldtype)">
		<FormControl type="select" :options="optionsList[fieldtype]" v-model="value" />
	</template>

	<template v-else-if="typeNumber.includes(fieldtype)">
		<FormControl type="number" v-model="value" />
	</template>
	<template v-else-if="typeDate.includes(fieldtype) && operator == 'between'">
		<DateRangePicker :value="value" @change="(range) => (value = range)" />
	</template>
	<template v-else-if="fieldtype == 'Date'">
		<DatePicker :value="value" @change="(date) => (value = date)" />
	</template>
	<template v-else-if="fieldtype == 'Datetime'">
		<DatetimePicker :value="value" @change="(date) => (value = date)" />
	</template>
	<template v-else-if="fieldtype == 'Link'">
		<Link
			:doctype="options[0]"
			:value="value"
			:class="'form-control'"
			@change="(val) => (value = val)"
		/>
	</template>
	<template v-else>
		<FormControl type="text" v-model="value" />
	</template>
</template>

<script setup>
import { ref, watch } from "vue"
import { FormControl } from "frappe-ui"

import DatePicker from "@/components/Controls/DatePicker.vue"
import DatetimePicker from "@/components/Controls/DatetimePicker.vue"
import DateRangePicker from "@/components/Controls/DateRangePicker.vue"
import Link from "@/components/Controls/Link.vue"

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

const typeNumber = ["Float", "Int", "Currency", "Percent"]
const typeDate = ["Date", "Datetime"]
</script>
