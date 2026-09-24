<!-- The panel's three built-ins before the record arrives: identity with its quick actions,
     then the two people rows, on PanelSection's padding and PeopleRow's grid. -->
<template>
	<div v-if="collapsed" class="flex flex-col items-center gap-1 py-3" data-record-panel-skeleton>
		<LoadingStatus />
		<Skeleton v-for="action in 3" :key="action" class="size-7 rounded-4" />
	</div>

	<div v-else class="flex flex-col" data-record-panel-skeleton>
		<LoadingStatus />
		<div class="flex flex-col gap-2.5 px-4 py-3">
			<div class="flex flex-col">
				<Skeleton class="my-[3px] h-4 w-40 rounded-1" />
				<Skeleton class="mb-0.5 mt-[5px] h-3 w-28 rounded-1" />
			</div>
			<div class="flex items-center gap-1">
				<Skeleton class="h-7 w-20 rounded-4" />
				<Skeleton class="h-7 w-24 rounded-4" />
				<Skeleton v-for="icon in 3" :key="icon" class="size-7 rounded-4" />
			</div>
		</div>

		<div class="flex flex-col gap-2.5 border-t border-outline-gray-1 px-4 py-3">
			<div
				v-for="row in 2"
				:key="row"
				class="grid h-7 grid-cols-[130px_1fr] items-center gap-2"
			>
				<div class="flex items-center gap-2">
					<Skeleton class="size-4 rounded-1" />
					<Skeleton class="h-3 w-20 rounded-1" />
				</div>
				<Skeleton class="mx-1.5 h-3 w-24 rounded-1" />
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { Skeleton } from "frappe-ui";
import LoadingStatus from "@/shell/LoadingStatus.vue";

defineProps<{ collapsed: boolean }>();
</script>
