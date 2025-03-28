<template>
	<div class="flex h-screen overflow-hidden">
		<div
			ref="leftPane"
			:style="{ width: leftPaneWidth + 'px' }"
			class="flex-shrink-0 border-r border-gray-200"
		>
			<slot name="left"></slot>
		</div>
		<div
			ref="resizer"
			class="w-[1px] flex-shrink-0 cursor-col-resize bg-gray-200 hover:bg-gray-300"
			@mousedown="startResize"
		></div>
		<div class="flex-grow overflow-auto">
			<slot name="right"></slot>
		</div>
	</div>
</template>

<script setup>
import { ref, onMounted } from "vue"

const leftPane = ref(null)
const resizer = ref(null)
const leftPaneWidth = ref(600) // Initial width

let startX = 0

const startResize = (e) => {
	startX = e.clientX
	window.addEventListener("mousemove", resize)
	window.addEventListener("mouseup", stopResize)
}

const resize = (e) => {
	const delta = e.clientX - startX
	leftPaneWidth.value = Math.max(100, leftPane.value.offsetWidth + delta) // Minimum width of 100px
	startX = e.clientX
}

const stopResize = () => {
	window.removeEventListener("mousemove", resize)
	window.removeEventListener("mouseup", stopResize)
}

onMounted(() => {
	if (leftPane.value) {
		leftPaneWidth.value = leftPane.value.offsetWidth
	}
})
</script>
