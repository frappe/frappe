<template>
	<div class="flex h-full flex-col">
		<div v-for="screen in store.appScreens" :key="screen.name">
			<div class="flex cursor-pointer items-center gap-2 p-2">
				<span>{{ screen.screen_title }}</span>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import useStudioStore from "@/stores/studioStore"

const store = useStudioStore()
</script>
