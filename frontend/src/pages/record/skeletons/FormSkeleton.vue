<!-- A form's fields before its layout arrives: label and input pairs at FormLayout's own
     heights and gaps. The caller supplies the container the real sections sit in. -->
<template>
	<div data-form-skeleton>
		<Skeleton v-if="heading" class="my-0.5 h-[15px] w-24 rounded-1" />
		<div
			class="grid gap-4"
			:class="[columns === 2 ? 'sm:grid-cols-2' : '', heading ? 'mt-6' : '']"
		>
			<div v-for="field in fields" :key="field" class="flex flex-col gap-1.5">
				<Skeleton class="my-px h-[13px] w-20 rounded-1" />
				<Skeleton class="h-7 w-full rounded-4" />
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { Skeleton } from "frappe-ui";

defineProps<{
	columns: 1 | 2;
	fields: number;
	/** A bar for the first section's label above the fields. */
	heading?: boolean;
}>();
</script>
