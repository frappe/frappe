<template>
	<div class="studio h-screen flex-col overflow-hidden bg-gray-100">
		<StudioToolbar class="relative z-30" />
		<div class="flex flex-col">
			<StudioLeftPanel class="absolute bottom-0 left-0 top-[var(--toolbar-height)] bg-white" />
			<StudioCanvas
				class="canvas-container absolute bottom-0 top-[var(--toolbar-height)] flex justify-center overflow-hidden bg-gray-200 p-10 left-[280px] right-[275px]"
			/>
		</div>
	</div>
</template>

<script setup>
import StudioToolbar from "@/components/StudioToolbar.vue"
import StudioLeftPanel from "@/components/StudioLeftPanel.vue"
import StudioCanvas from "@/components/StudioCanvas.vue"
</script>

<style>
.studio {
	--left-panel-width: 17rem;
	--right-panel-width: 20rem;
	--toolbar-height: 3.5rem;
}
</style>
