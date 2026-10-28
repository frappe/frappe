<template>
	<TextInput
		:class="{ group: url }"
		:modelValue="shown"
		:type="attrs.type"
		:inputmode="attrs.inputmode"
		:label="field.label"
		:description="field.description"
		:placeholder="field.placeholder"
		:required="field.reqd"
		:error="error"
		:disabled="field.readOnly"
		@update:modelValue="onInput"
		@change="(e: Event) => onCommit((e.target as HTMLInputElement).value)"
		@focus="onFocus"
		@blur="focused = false"
	>
		<template v-if="url" #suffix>
			<DataOpenLink
				v-if="address?.kind === 'web'"
				:address="address"
				class="hidden focus-visible:grid group-focus-within:grid group-hover:grid"
			/>
		</template>
	</TextInput>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { TextInput } from "frappe-ui";
import { dataHref, dataInputAttrs, dataOption, groupIban, stripIban } from "./dataOptions";
import DataOpenLink from "./DataOpenLink.vue";
import type { FieldComponentEmits, FieldComponentProps } from "./types";

const props = defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();

const option = computed(() => dataOption(props.field));
const attrs = computed(() => dataInputAttrs(option.value));
const iban = computed(() => option.value === "IBAN");
const url = computed(() => option.value === "URL");
const address = computed(() => dataHref(props.field, props.modelValue));

// An IBAN shows grouped, but regrouping while the person types would move the caret.
const focused = ref(false);
const draft = ref("");
const shown = computed(() => {
	if (!iban.value) return props.modelValue;
	return focused.value ? draft.value : groupIban(props.modelValue ?? "");
});

watch(
	() => props.modelValue,
	(value) => {
		if (focused.value && stripIban(draft.value) !== (value ?? ""))
			draft.value = groupIban(value ?? "");
	}
);

function onFocus() {
	draft.value = groupIban(props.modelValue ?? "");
	focused.value = true;
}

function onInput(value: string) {
	draft.value = value;
	emit("update:modelValue", iban.value ? stripIban(value) : value);
}

function onCommit(value: string) {
	emit("change", iban.value ? stripIban(value) : value);
}
</script>
