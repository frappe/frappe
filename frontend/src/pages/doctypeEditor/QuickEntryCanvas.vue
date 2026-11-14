<!-- The Quick entry layout inside a frame of the Create dialog: 576px, its title, × and the inert Create button.
     A read-only value takes the inputs' fill in dark, where the frame's own fill would hide it. -->
<template>
	<div
		class="mx-auto w-full max-w-xl rounded-7 bg-surface-elevation-1 shadow-xl dark:[&_[data-slot=read-value]]:bg-surface-gray-2"
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
			<CanvasForm :canvas="canvas" />
		</div>
		<div class="flex justify-end px-4 pb-7 pt-4 sm:px-6" aria-hidden="true">
			<Button variant="solid" :label="__('Create')" inert tabindex="-1" />
		</div>
	</div>
</template>

<script setup lang="ts">
import { Button, Icon } from "frappe-ui";
import { __ } from "@/i18n";
import CanvasForm from "./CanvasForm.vue";
import type { DesignCanvas } from "./designCanvas";

defineProps<{ canvas: DesignCanvas }>();
</script>
