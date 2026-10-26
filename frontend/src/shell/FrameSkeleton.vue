<!-- The frame while a page's code loads: the header row the page fills, so its arrival moves nothing. -->
<template>
	<PageFrame :scroll="false">
		<template #header>
			<div class="flex h-7 min-w-0 flex-1 items-center" data-frame-skeleton>
				<Skeleton class="h-4 w-16 rounded-1" />
			</div>
		</template>
		<LoadingStatus />
	</PageFrame>
</template>

<script setup lang="ts">
import { Skeleton } from "frappe-ui";
import LoadingStatus from "./LoadingStatus.vue";
import PageFrame from "./PageFrame.vue";

// A page's props reach its loading state too; they mean nothing here.
defineOptions({ inheritAttrs: false });
</script>
