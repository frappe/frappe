<!-- The bands of one place on the frame's column, each in a bare wrapper that carries the page gutter unless the band opted out. -->
<template>
	<div
		v-for="band in bands"
		:key="band.name"
		:class="band.gutter === false ? '' : pageGutter"
		:data-frame-band="band.name"
	>
		<component :is="band.component" v-bind="{ ...band.props, page }" />
	</div>
</template>

<script setup lang="ts">
import type { FrameItem, RecordPageApi } from "@/recordPage";
import { pageGutter } from "@/shell/PageFrame.vue";

defineProps<{
	bands: FrameItem[];
	/** Handed to every band beside its own props, as a header component receives it. */
	page: RecordPageApi;
}>();
</script>
