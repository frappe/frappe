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
			>
				<StudioComponent
					class="h-full min-h-[inherit]"
					v-if="rootComponent"
					:componentName="rootComponent"
				/>
			</div>
		</div>
	</div>
</template>

<script setup>
import { ref, reactive } from "vue"
import { useDropZone } from "@vueuse/core"
import StudioComponent from "@/components/StudioComponent.vue"

const canvasContainer = ref(null)
const canvas = ref(null)
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

const rootComponent = ref(null)

const { isOverDropZone } = useDropZone(canvasContainer, {
	onDrop: (_files, ev) => {
		rootComponent.value = ev.dataTransfer.getData("componentName")
	},
})
</script>
