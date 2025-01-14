<!-- Used as Autocomplete, Barcode, Color, Currency, Data, Date, Duration, Link, Dynamic Link, Float, Int, Password, Percent, Time, Read Only, HTML Control -->
<script setup>
import { ref, useSlots } from "vue";

const props = defineProps(["df", "value", "read_only"]);
let slots = useSlots();
let time_zone = ref("");
let placeholder = ref("");

if (props.df.fieldtype === "Datetime") {
	let time_zone_text = frappe.boot.time_zone
		? frappe.boot.time_zone.user
		: frappe.sys_defaults.time_zone;
	time_zone.value = time_zone_text;
}

if (props.df.fieldtype === "Color") {
	placeholder.value = __("Choose a color");
}
if (props.df.fieldtype === "Icon") {
	placeholder.value = __("Choose an icon");
}
</script>

<template>
	<div class="control frappe-control" :class="{ editable: slots.label }">
		<!-- label -->
		<div v-if="slots.label" class="field-controls">
			<slot name="label" />
			<slot name="actions" />
		</div>
		<div v-else class="control-label label" :class="{ reqd: df.reqd }">{{ __(df.label) }}</div>

		<!-- data input -->
		<input
			v-if="slots.label"
			class="form-control"
			type="text"
			:style="{ height: df.fieldtype == 'Table MultiSelect' ? '42px' : '' }"
			:placeholder="__(placeholder)"
			readonly
		/>
		<input
			v-else
			class="form-control"
			type="text"
			:value="value"
			:disabled="read_only || df.read_only"
			@input="(event) => $emit('update:modelValue', event.target.value)"
		/>
		<input
			v-if="slots.label && df.fieldtype === 'Barcode'"
			class="mt-2 form-control"
			type="text"
			:style="{ height: '110px' }"
			readonly
		/>

		<!-- description -->
		<div v-if="df.description" class="mt-2 description" v-html="__(df.description)" />

		<!-- timezone for datetime field -->
		<div
			v-if="time_zone"
			:class="['time-zone', !df.description ? 'mt-2' : '']"
			v-html="time_zone"
		/>

		<!-- color selector icon -->
		<div class="selected-color no-value" />

		<!-- icon selector icon -->
		<div
			v-if="df.fieldtype == 'Icon'"
			class="selected-icon no-value"
			v-html="frappe.utils.icon('folder-normal', 'md')"
		/>
		<!-- phone selector icon -->
		<div
			v-if="df.fieldtype == 'Phone'"
			class="selected-phone no-value"
			v-html="frappe.utils.icon('down', 'sm')"
		/>
	</div>
</template>

<style lang="scss" scoped>
.selected-color {
	background-color: transparent;
	top: 30px !important;
}

.selected-phone {
	top: 32px !important;
}
</style>
