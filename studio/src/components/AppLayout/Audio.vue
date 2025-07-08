<template>
	<div class="w-full">
		<audio
			ref="audioElement"
			:src="file"
			@timeupdate="onTimeUpdate"
			@loadedmetadata="onLoadedMetadata"
		></audio>
		<div class="mb-6 flex items-center justify-center space-x-8">
			<button
				@click="previousTrack"
				class="flex h-10 w-10 items-center justify-center rounded-full hover:bg-gray-50 focus:outline-none"
			>
				<FeatherIcon name="skip-back" class="h-6 w-6 fill-gray-800 stroke-gray-800" />
			</button>
			<button
				@click="togglePlay"
				class="flex h-16 w-16 items-center justify-center rounded-full bg-gray-800 focus:outline-none"
			>
				<FeatherIcon :name="isPlaying ? 'pause' : 'play'" class="h-6 w-6 fill-white stroke-white" />
			</button>
			<button
				@click="nextTrack"
				class="flex h-10 w-10 items-center justify-center rounded-full hover:bg-gray-50 focus:outline-none"
			>
				<FeatherIcon name="skip-forward" class="h-6 w-6 fill-gray-800 stroke-gray-800" />
			</button>
		</div>
		<div class="relative w-full">
			<input
				type="range"
				min="0"
				:max="duration"
				:value="currentTime"
				@input="seek"
				class="h-2 w-full cursor-pointer rounded-lg bg-gray-200 accent-gray-800 dark:bg-gray-700"
			/>
		</div>
		<div class="mt-2 flex justify-between text-sm text-gray-700">
			<span>{{ formatTime(currentTime) }}</span>
			<span>{{ formatTime(duration) }}</span>
		</div>
	</div>
</template>

<script setup lang="ts">
import { FeatherIcon } from "frappe-ui"
import { ref, onMounted, watch } from "vue"

import type { AudioProps } from "@/types/studio_components/Audio"

const props = defineProps<AudioProps>()
const emit = defineEmits(["previous", "next"])

const audioElement = ref<HTMLAudioElement | null>(null)
const isPlaying = ref(false)
const currentTime = ref(0)
const duration = ref(0)

const togglePlay = () => {
	if (!audioElement.value) return
	if (audioElement.value.paused) {
		audioElement.value.play()
	} else {
		audioElement.value.pause()
	}
	isPlaying.value = !audioElement.value.paused
}

const onTimeUpdate = () => {
	currentTime.value = audioElement.value?.currentTime || 0
}

const onLoadedMetadata = () => {
	duration.value = audioElement.value?.duration || 0
}

const formatTime = (time: number) => {
	const minutes = Math.floor(time / 60)
	const seconds = Math.floor(time % 60)
	return `${minutes}:${seconds.toString().padStart(2, "0")}`
}

const previousTrack = () => {
	emit("previous")
}

const nextTrack = () => {
	emit("next")
}

const seek = (event: Event) => {
	if (!audioElement.value) return
	const newTime = parseFloat((event.target as HTMLInputElement).value)
	audioElement.value.currentTime = newTime
	currentTime.value = newTime
}

watch(
	() => props.file,
	() => {
		// Reset player when audio file changes
		currentTime.value = 0
		isPlaying.value = false
	},
)

onMounted(() => {
	if (audioElement.value) {
		audioElement.value.addEventListener("play", () => (isPlaying.value = true))
		audioElement.value.addEventListener("pause", () => (isPlaying.value = false))
	}
})
</script>

<style scoped>
input[type="range"]::-webkit-slider-thumb {
	-webkit-appearance: none;
	appearance: none;
	width: 15px;
	height: 15px;
	cursor: pointer;
	border-radius: 50%;
}

input[type="range"]::-moz-range-thumb {
	width: 15px;
	height: 15px;
	cursor: pointer;
	border-radius: 50%;
}
</style>
