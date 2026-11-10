<template>
	<LinkValue
		v-if="field.readOnly"
		:text="title ?? value"
		:href="record.href.value"
		:label="field.label"
		:description="field.description"
		:required="field.reqd"
		:error="error"
		@open="record.open"
	>
		<template #prefix>
			<LinkMark
				class="me-1.5"
				:source="field.linkMark"
				:value="mark"
				:text="title ?? value"
			/>
		</template>
	</LinkValue>
	<Link
		v-else
		ref="link"
		v-model="value"
		v-model:open="open"
		:doctype="field.options ?? ''"
		:filters="field.filters"
		:title="title"
		:idLabels="isName"
		:label="field.label"
		:description="field.description"
		:placeholder="field.placeholder"
		:required="field.reqd"
		:error="error"
		:href="record.href.value"
		:creatable="linkCreate.creatable.value"
		@create="linkCreate.create"
		@redirect="record.open"
	>
		<template v-if="field.description && !error?.length" #description>
			<FieldDescription :html="field.description" />
		</template>
		<template #prefix>
			<LinkMark
				class="me-1.5"
				:source="field.linkMark"
				:value="mark"
				:text="title ?? value"
			/>
		</template>
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
import { useLinkMark } from "./useLinkMark";
import { useRecordLink } from "./useRecordLink";
import LinkMark from "./LinkMark.vue";
import LinkValue from "./LinkValue.vue";
import FieldDescription from "./FieldDescription.vue";

const props = defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();

const titles = inject(LinkTitlesKey, null);
const link = ref<LinkExposed | null>(null);
const open = ref(false);

// `name` stores the ID, so show the ID, not the title.
const isName = computed(() => props.field.fieldname === "name");

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

const record = useRecordLink(
	() => props.field.options ?? "",
	() => value.value
);

const mark = useLinkMark(
	() => props.field,
	() => props.modelValue
);

const title = computed(() =>
	isName.value
		? undefined
		: ((props.modelValue
				? titles?.value[`${props.field.options}::${props.modelValue}`]
				: undefined) ?? linkCreate.title(props.modelValue))
);
</script>
