<template>
	<div class="flex flex-col gap-4 p-6">
		<h3 class="text-lg-semibold text-ink-gray-9">Tag</h3>
		<div class="flex flex-wrap items-center gap-2">
			<Tag v-for="color in TAG_COLOR_NAMES" :key="color" :label="color" :color="color" />
			<Tag label="No color" />
			<Tag label="With suffix" color="Blue">
				<template #suffix><LucideX class="size-3" /></template>
			</Tag>
		</div>
	</div>
</template>

<script setup lang="ts">
import { TAG_COLOR_NAMES } from "../colors";
import Tag from "../Tag.vue";
</script>
