<!-- A Table or Table MultiSelect field on the parent's canvas: the record page's own control, read-only
     with no rows, drawn from the child's fields as its editor has them, so a grid's columns show.
     While the child's meta loads, or when it failed, the field says so in place of its columns. The
     grid is inert; the failed block is not, so its Try again works. -->
<template>
	<div v-if="child.loading.value" class="flex flex-col gap-1.5" data-child-columns="loading">
		<LoadingStatus />
		<FormLabel :label="label" :required="Boolean(field.reqd)" />
		<Skeleton class="h-7 w-full rounded-4" />
	</div>
	<div
		v-else-if="child.error.value"
		class="flex flex-col items-start gap-1.5"
		data-child-columns="failed"
	>
		<FormLabel :label="label" :required="Boolean(field.reqd)" />
		<ErrorMessage
			:message="
				asErrorHtml(__('Could not load the columns of {0}.', [__(field.options ?? '')]))
			"
		/>
		<Button :label="__('Try again')" @click="child.reload()" />
	</div>
	<div v-else class="pointer-events-none" inert>
		<FormLayoutField :field="node">
			<template v-if="$slots['label-after']" #label-after
				><slot name="label-after"
			/></template>
		</FormLayoutField>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { Button, ErrorMessage, FormLabel, Skeleton } from "frappe-ui";
import { FormLayoutField, mapField } from "@framework/ui/FormLayout";
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import { __ } from "@/i18n";
import { asErrorHtml } from "./asErrorHtml";
import LoadingStatus from "@/shell/LoadingStatus.vue";
import { useChildFields } from "./childFields";

const props = defineProps<{ field: RawMetaField }>();

const child = useChildFields(() => props.field.options);
const label = computed(() => __(props.field.label || props.field.fieldname));
const node = computed(() => {
	const { options } = props.field;
	const fields = child.fields.value;
	return {
		...mapField(props.field, options && fields ? { [options]: fields } : {}),
		readOnly: true,
	};
});
</script>
