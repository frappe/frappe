<template>
	<TextInput
		:class="{ group: url }"
		:modelValue="shown"
		:type="attrs.type"
		:inputmode="attrs.inputmode"
		v-bind="frame"
		:placeholder="field.placeholder"
		:required="field.reqd"
		:disabled="field.readOnly"
		@update:modelValue="onInput"
		@change="(e: Event) => onCommit((e.target as HTMLInputElement).value)"
		@focus="onFocus"
		@blur="focused = false"
	>
		<template v-if="!panel && field.description && !error?.length" #description>
			<FieldDescription :html="field.description" />
		</template>
		<template v-if="url || phone" #suffix>
			<FieldActions v-if="phone && !row" :field="field" :value="modelValue" />
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
import FieldActions from "./FieldActions.vue";
import type { FieldComponentEmits, FieldComponentProps } from "./types";
import FieldDescription from "./FieldDescription.vue";
import { useInputFrame } from "./inputFrame";

const props = defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();
const frame = useInputFrame(props);

const option = computed(() => dataOption(props.field));
const attrs = computed(() => dataInputAttrs(option.value));
const iban = computed(() => option.value === "IBAN");
const url = computed(() => option.value === "URL");
const phone = computed(() => option.value === "Phone");
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
