<!-- Settings rows while a block loads, each as tall as a loaded row. -->
<template>
	<div aria-hidden="true">
		<div
			v-for="row in rows"
			:key="row"
			class="flex items-center gap-8 border-b border-outline-gray-1 py-3.5 last:border-b-0"
		>
			<Skeleton class="h-4 w-36 rounded-1" />
			<Skeleton class="ml-auto h-7 w-56 rounded-4" />
		</div>
	</div>
</template>

<script setup lang="ts">
import { Skeleton } from "frappe-ui";

defineProps<{ rows: number }>();
</script>
