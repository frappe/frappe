<script setup>
import { ref, nextTick } from "vue";
import { useStore } from "../store";
let store = useStore();

const props = defineProps({
	text: {
		type: String,
	},
	placeholder: {
		default: __("No Label"),
	},
	empty_label: {
		default: __("No Label"),
	},
});

let editing = ref(false);
let input_text = ref(null);

function focus_on_label() {
	if (!store.read_only) {
		editing.value = true;
		nextTick(() => input_text.value.focus());
	}
}

defineExpose({ focus_on_label });
</script>

<template>
	<div @dblclick="focus_on_label" :title="__('Double click to edit label')">
		<input
			v-if="editing"
			class="input-text bg-transparent"
			ref="input_text"
			:disabled="store.read_only"
			type="text"
			:placeholder="__(placeholder)"
			:value="text"
			@input="(event) => $emit('update:modelValue', event.target.value)"
			@keydown.enter="editing = false"
			@blur="editing = false"
			@click.stop
		/>
		<span v-else-if="text" v-html="text"></span>
		<i v-else class="text-muted">
			{{ __(empty_label) }}
		</i>
	</div>
</template>

<style lang="scss" scoped>
.input-text {
	width: 180px;
	max-width: 100%;

	border: none;
	padding: 0px !important;
	@supports (field-sizing: content) {
		field-sizing: content;
		width: auto;
		min-width: 50px;
	}

	&:focus {
		outline: none;
		background-color: inherit;
	}

	&::placeholder {
		font-style: italic;
		font-weight: normal;
	}
}
</style>
