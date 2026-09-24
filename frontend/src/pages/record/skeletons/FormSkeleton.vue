<!-- A form's fields before its layout arrives: label and input pairs at FormLayout's own
     heights and gaps. The caller supplies the container the real sections sit in. -->
<template>
	<div data-form-skeleton>
		<LoadingStatus />
		<div class="grid gap-4" :class="{ 'sm:grid-cols-2': columns === 2 }">
			<div v-for="field in fields" :key="field" class="flex flex-col gap-1.5">
				<Skeleton class="my-px h-[13px] w-20 rounded-1" />
				<Skeleton class="h-7 w-full rounded-4" />
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { Skeleton } from "frappe-ui";
import LoadingStatus from "@/shell/LoadingStatus.vue";

defineProps<{
	columns: 1 | 2;
	fields: number;
}>();
</script>
