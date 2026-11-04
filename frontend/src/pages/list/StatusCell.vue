<!-- A status or workflow state column's cell: the value as a coloured badge. -->
<template>
	<Badge :label="text" :theme="theme" />
</template>

<script setup lang="ts">
import type { FieldMeta } from "@framework/ui/fields/types";
import { useFieldDisplay } from "@framework/ui/FormLayout";
import { Badge } from "frappe-ui";
import type { BadgeProps } from "frappe-ui";
import { computed } from "vue";

const props = defineProps<{
	field: FieldMeta;
	row: Record<string, unknown>;
	theme: BadgeProps["theme"];
}>();

const display = useFieldDisplay();

const text = computed(() =>
	display(props.field, props.row[props.field.fieldname], { row: props.row })
);
</script>
