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
import {
	numberTypes,
	dateTypes,
	timespanOptionsList,
	checkOptionsList,
	isOptionsList,
} from "@/stores/list_filter"
import { ref, watch } from "vue"
import { FormControl, DatePicker } from "frappe-ui"

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
const optionsList = {
	timespan: timespanOptionsList,
	is: isOptionsList,
	Check: checkOptionsList,
	Select: props.options,
}
</script>
