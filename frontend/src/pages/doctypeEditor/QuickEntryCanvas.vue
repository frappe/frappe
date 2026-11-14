<!-- The Quick entry layout inside a frame of the Create dialog: 576px, its title and ×. -->
<template>
	<div
		class="mx-auto w-full max-w-xl rounded-7 bg-surface-elevation-1 shadow-xl"
		data-canvas-quick-entry
	>
		<div class="px-4 pb-6 pt-5 sm:px-6">
			<div class="mb-6 flex items-center justify-between gap-2">
				<p class="text-2xl-semibold leading-6 text-ink-gray-8">
					{{ __("New {0}", [__(canvas.state.doctype)]) }}
				</p>
				<span class="grid size-7 place-items-center" aria-hidden="true">
					<Icon name="lucide-x" class="size-4 text-ink-gray-9" />
				</span>
			</div>
			<CanvasForm :canvas="canvas" :tabbed="false" />
		</div>
	</div>
</template>

<script setup lang="ts">
import { Icon } from "frappe-ui";
import { __ } from "@/i18n";
import CanvasForm from "./CanvasForm.vue";
import type { DesignCanvas } from "./designCanvas";

defineProps<{ canvas: DesignCanvas }>();
</script>
