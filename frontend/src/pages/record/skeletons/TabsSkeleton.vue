<!-- The tab strip and the Details form before the page's first replay, in the strip's
     padding and the form's column, so the real ones land in place. -->
<template>
	<div class="flex min-h-0 flex-1 flex-col">
		<div
			class="shrink-0 border-b border-outline-gray-1 px-[--page-gutter] py-2"
			data-record-tabs-skeleton
		>
			<div class="flex h-7 items-center gap-5">
				<Skeleton v-for="n in 4" :key="n" class="h-4 w-16 rounded-4" />
			</div>
		</div>
		<FormSkeleton
			:columns="2"
			:fields="8"
			heading
			class="mx-auto w-full max-w-3xl px-[--page-gutter] py-6"
		/>
	</div>
</template>

<script setup lang="ts">
import { Skeleton } from "frappe-ui";
import FormSkeleton from "./FormSkeleton.vue";
</script>
