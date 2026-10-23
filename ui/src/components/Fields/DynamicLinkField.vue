<template>
	<Link
		ref="link"
		v-model="value"
		v-model:open="open"
		:doctype="doctype"
		:filters="field.filters"
		:title="linkCreate.title(value)"
		:label="field.label"
		:description="field.description"
		:placeholder="field.placeholder"
		:required="field.reqd"
		:disabled="field.readOnly || !doctype"
		:creatable="linkCreate.creatable.value"
		@create="linkCreate.create"
	>
		<template #item-create="{ query }">
			<span class="truncate">{{ linkCreate.label(query) }}</span>
		</template>
	</Link>
</template>

<script setup lang="ts">
// Dynamic Link: the target doctype is named by a sibling field (`field.options`),
// resolved via `pickSiblingValue` (row → doc → parent). Disabled until it has a value.
import { computed, inject, ref } from "vue";
import { Link } from "../Link";
import type { LinkExposed } from "../Link";
import { DocKey, ParentDocKey } from "./types";
import { pickSiblingValue } from "../FormLayout/pickSiblingValue";
import type { FieldComponentEmits, FieldComponentProps } from "./types";
import { useLinkCreate } from "./useLinkCreate";

const props = defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();

const doc = inject(DocKey, null);
const parentDoc = inject(ParentDocKey, null);
const link = ref<LinkExposed | null>(null);
const open = ref(false);

const doctype = computed<string>(() => {
	const sibling = props.field.options;
	const dt = sibling
		? pickSiblingValue(
				{ row: props.row, doc: doc?.value, parentDoc: parentDoc?.value },
				sibling
		  )
		: null;
	return typeof dt === "string" ? dt : "";
});

const value = computed<string | null>({
	get: () => props.modelValue ?? null,
	set: (v) => {
		emit("update:modelValue", v);
		emit("change", v);
	},
});

const linkCreate = useLinkCreate({
	doctype,
	filters: () => props.field.filters,
	disabled: () => Boolean(props.field.readOnly) || !doctype.value,
	open,
	link,
	select: (name) => (value.value = name),
});
</script>
