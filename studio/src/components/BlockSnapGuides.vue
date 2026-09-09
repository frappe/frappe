<template>
	<div>
		<div
			v-if="canvasStore.guides.showX && canvasStore.guides.x >= 0"
			class="pointer-events-none fixed bottom-0 top-0 z-[250] w-px bg-surface-red-5"
			:style="{ left: canvasStore.guides.x + 'px' }"
		/>
		<div
			v-if="canvasStore.guides.showY && canvasStore.guides.y >= 0"
			class="pointer-events-none fixed left-0 right-0 z-[250] h-px bg-surface-red-5"
			:style="{ top: canvasStore.guides.y + 'px' }"
		/>
	</div>
</template>

<script setup lang="ts">
import useCanvasStore from "@/stores/canvasStore"

const canvasStore = useCanvasStore()
</script>
