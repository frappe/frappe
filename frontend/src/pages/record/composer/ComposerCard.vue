<!-- The open writer, docked at the foot of the tab: a drag handle on its top edge, its name, and collapse. -->
<template>
	<div
		ref="card"
		class="pointer-events-auto relative flex flex-col rounded-7 border border-outline-gray-2 bg-surface-base shadow-lg"
		:class="{ 'select-none': dock.dragging.value }"
		:style="{ height: `${dock.height.value}px` }"
		data-composer-card
	>
		<button
			type="button"
			class="absolute left-1/2 top-0 z-10 flex h-3 w-24 -translate-x-1/2 cursor-ns-resize touch-none items-center justify-center opacity-60 hover:opacity-100"
			:aria-label="__('Resize the composer')"
			data-composer-handle
			@pointerdown="dock.begin($event, card?.offsetHeight ?? dock.height.value)"
			@pointermove="dock.move"
			@pointerup="dock.end"
			@pointercancel="dock.end"
		>
			<span class="h-1 w-10 rounded-full bg-surface-gray-4" />
		</button>

		<div class="flex shrink-0 items-center gap-2 px-3 pt-3">
			<span
				v-if="writer.icon"
				class="size-4 text-ink-gray-5"
				:class="writer.icon"
				aria-hidden="true"
			/>
			<span class="truncate text-base font-medium text-ink-gray-8">{{ writer.label }}</span>
			<div class="ml-auto flex shrink-0">
				<Tooltip :text="__('Collapse')">
					<Button
						icon="lucide-chevrons-down-up"
						variant="ghost"
						:label="__('Collapse')"
						data-composer-collapse
						@click="emit('collapse')"
					/>
				</Tooltip>
			</div>
		</div>

		<div class="flex min-h-0 flex-1 flex-col">
			<slot />
		</div>
	</div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { Button, Tooltip } from "frappe-ui";
import type { WriterItem } from "@/recordPage/types";
import { __ } from "@/i18n";
import { useDockHeight } from "./useDockHeight";

const props = defineProps<{ writer: WriterItem; user: string }>();

const emit = defineEmits<{ collapse: [] }>();

const card = ref<HTMLElement | null>(null);
const dock = useDockHeight(props.user);
</script>
