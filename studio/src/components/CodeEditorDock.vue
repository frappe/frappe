<template>
	<!-- A full-height code editor docked beside the left panel, shared by the file explorer and the
	     page script so both edit code the same way. -->
	<Teleport to="#studio-code-editor-outlet">
		<div
			v-if="visible"
			class="absolute bottom-0 top-[var(--toolbar-height)] z-20 flex flex-col border-r border-outline-gray-2 bg-surface-base"
			:style="{ left: `${panelLeft}px`, width: `${editorWidth}px` }"
		>
			<PanelResizer
				side="right"
				:dimension="editorWidth"
				:minDimension="360"
				:maxDimension="maxEditorWidth"
				@resize="editorWidth = $event"
				@dblclick="toggleFullWidth"
			/>
			<div
				class="flex select-none items-center justify-between gap-2 border-b border-outline-gray-2 px-3 py-2"
				@dblclick="toggleFullWidth"
			>
				<div class="flex min-w-0 items-center gap-1.5">
					<slot name="title" />
				</div>
				<div class="flex shrink-0 items-center gap-1" @dblclick.stop>
					<slot name="actions" />
				</div>
			</div>
			<slot name="banner" />
			<div class="relative min-h-0 flex-1 overflow-hidden">
				<Code
					:modelValue="modelValue"
					:language="language"
					height="100%"
					maxHeight="100%"
					:emitOnChange="true"
					:borderless="true"
					:readonly="readonly"
					:completions="completions"
					@update:modelValue="emit('update:modelValue', $event)"
					@save="emit('save')"
				/>
			</div>
		</div>
	</Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch } from "vue"
import { useWindowSize } from "@vueuse/core"
import Code from "@/components/Code.vue"
import PanelResizer from "@/components/PanelResizer.vue"
import useStudioStore from "@/stores/studioStore"

const props = withDefaults(
	defineProps<{
		open: boolean
		modelValue: string
		language?: "json" | "javascript" | "html" | "css" | "vue"
		completions?: Function | null
		readonly?: boolean
		// Dock against the primary icon rail instead of beside the secondary panel — for editors
		// (e.g. the page script) that replace the panel content rather than sit next to it.
		railLeft?: boolean
	}>(),
	{
		language: "javascript",
		completions: null,
		readonly: false,
		railLeft: false,
	},
)
const emit = defineEmits(["update:modelValue", "save"])

const store = useStudioStore()

const visible = computed(
	() => props.open && store.studioLayout.showLeftPanel && store.studioLayout.leftPanelActiveTab === "Code",
)

const RAIL_WIDTH = 48
const panelLeft = computed(() => (props.railLeft ? RAIL_WIDTH : store.studioLayout.leftPanelWidth))
const EDITOR_WIDTH = 520
const editorWidth = ref(EDITOR_WIDTH)
// Cap the editor so its right edge stops at the app's right edge (it may cover the right panel,
// but never overflow the window). Recomputes as the window or left panel resizes.
const { width: viewportWidth } = useWindowSize()
const maxEditorWidth = computed(() => Math.max(360, viewportWidth.value - panelLeft.value))
const restoreWidth = ref(EDITOR_WIDTH)

watch(
	maxEditorWidth,
	(max) => {
		if (editorWidth.value > max) editorWidth.value = max
	},
	{ immediate: true },
)

// Double-click snaps to full width; double-click again restores the previous width.
function toggleFullWidth() {
	if (editorWidth.value >= maxEditorWidth.value - 1) {
		editorWidth.value = Math.min(restoreWidth.value, maxEditorWidth.value)
	} else {
		restoreWidth.value = editorWidth.value
		editorWidth.value = maxEditorWidth.value
	}
}
</script>
