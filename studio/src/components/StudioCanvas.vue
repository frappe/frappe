<template>
	<div ref="canvasContainer">
		<div class="overlay absolute" id="overlay" ref="overlay" />
		<div
			class="fixed flex gap-40"
			ref="canvas"
			:style="{
				transformOrigin: 'center top',
				transform: `scale(${canvasProps.scale}) translate(${canvasProps.translateX}px, ${canvasProps.translateY}px)`,
			}"
		>
			<div
				class="canvas relative flex h-full rounded-md bg-white shadow-2xl min-h-[1000px] w-[1400px]"
				:style="{
					background: canvasProps.background,
				}"
			></div>
		</div>
	</div>
</template>

<script setup>
import { ref, reactive } from "vue"

const overlay = ref(null)
const canvasProps = reactive({
	overlayElement: null,
	background: "#fff",
	scale: 0.337,
	translateX: 0,
	translateY: 81.3056,
	settingCanvas: true,
	scaling: false,
	panning: false,
})
</script>
