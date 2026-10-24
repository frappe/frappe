<template>
	<Link
		ref="link"
		v-model="value"
		v-model:open="open"
		:doctype="field.options ?? ''"
		:filters="field.filters"
		:title="title"
		:label="field.label"
		:description="field.description"
		:placeholder="field.placeholder"
		:required="field.reqd"
		:error="error"
		:disabled="field.readOnly"
		:creatable="linkCreate.creatable.value"
		@create="linkCreate.create"
	>
		<!-- Forward any slots (e.g. a #prefix affordance) on to the Link control. -->
		<template v-for="(_, name) in $slots" #[name]="slotProps" :key="name">
			<slot :name="name" v-bind="slotProps" />
		</template>
		<template #item-create="{ query }">
			<span class="truncate">{{ linkCreate.label(query) }}</span>
		</template>
	</Link>
</template>

<script setup lang="ts">
import { computed, inject, ref } from "vue";
import { Link } from "../Link";
import type { LinkExposed } from "../Link";
import { LinkTitlesKey } from "./types";
import type { FieldComponentEmits, FieldComponentProps } from "./types";
import { useLinkCreate } from "./useLinkCreate";

const props = defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();

const titles = inject(LinkTitlesKey, null);
const link = ref<LinkExposed | null>(null);
const open = ref(false);

const value = computed<string | null>({
	get: () => props.modelValue ?? null,
	// A selection is a commit for a picker: sync the value and fire the trigger.
	set: (v) => {
		emit("update:modelValue", v);
		emit("change", v);
	},
});

const linkCreate = useLinkCreate({
	doctype: () => props.field.options ?? "",
	filters: () => props.field.filters,
	disabled: () => Boolean(props.field.readOnly),
	open,
	link,
	select: (name) => (value.value = name),
});

const title = computed(
	() =>
		(props.modelValue
			? titles?.value[`${props.field.options}::${props.modelValue}`]
			: undefined) ?? linkCreate.title(props.modelValue)
);
</script>
