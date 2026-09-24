<!-- The header row before the record arrives: two crumbs and the star left, `⋯` and Save
     right, each in the box its real control takes. -->
<template>
	<div
		class="flex min-w-0 flex-1 items-center justify-between gap-3"
		data-record-header-skeleton
	>
		<LoadingStatus />
		<div class="flex min-w-0 flex-1 items-center gap-1">
			<div class="flex items-center pr-0.5">
				<Skeleton class="h-4 w-16 rounded-1" />
				<span class="mx-1 text-base text-ink-gray-4" aria-hidden="true">/</span>
				<Skeleton class="h-4 w-28 rounded-1" />
			</div>
			<div class="grid size-7 place-content-center">
				<Skeleton class="size-4 rounded-full" />
			</div>
		</div>
		<div class="flex shrink-0 items-center gap-2">
			<Skeleton class="size-7 rounded-4" />
			<Skeleton class="h-7 w-12 rounded-4" />
		</div>
	</div>
</template>

<script setup lang="ts">
import { Skeleton } from "frappe-ui";
import LoadingStatus from "@/shell/LoadingStatus.vue";
</script>
