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
				class="canvas relative flex h-full min-h-[1000px] w-[1400px] rounded-md bg-white shadow-2xl"
				:style="{
					background: canvasProps.background,
				}"
			>
				<StudioComponent class="h-full min-h-[inherit]" v-if="rootComponent" :block="rootComponent" />
			</div>
		</div>
	</div>
</template>

<script setup>
import { ref, reactive } from "vue"
import { useDropZone } from "@vueuse/core"
import StudioComponent from "@/components/StudioComponent.vue"

import useStore from "@/store"
import { getBlockCopy, getComponentBlock } from "@/utils/helpers"

const props = defineProps({
	componentTree: {
		type: Object,
		required: true,
	},
})
const store = useStore()

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

const rootComponent = ref(getBlockCopy(props.componentTree))

const { isOverDropZone } = useDropZone(canvasContainer, {
	onDrop: (_files, ev) => {
		let parentComponent = rootComponent.value

		const componentName = ev.dataTransfer?.getData("componentName")
		if (componentName) {
			const newBlock = getComponentBlock(componentName)
			parentComponent.addChild(newBlock)
		}
	},
})
</script>
