<!-- A Table or Table MultiSelect field on the parent's canvas: the record page's own control, read-only
     with no rows, drawn from the child's fields as its editor has them, so a grid's columns show. -->
<template>
	<FormLayoutField :field="node">
		<template v-if="$slots['label-after']" #label-after><slot name="label-after" /></template>
	</FormLayoutField>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { FormLayoutField, mapField } from "@framework/ui/FormLayout";
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import { useChildFields } from "./childFields";

const props = defineProps<{ field: RawMetaField }>();

const childFields = useChildFields(() => props.field.options);
const node = computed(() => {
	const { options } = props.field;
	const fields = childFields.value;
	return {
		...mapField(props.field, options && fields ? { [options]: fields } : {}),
		readOnly: true,
	};
});
</script>
