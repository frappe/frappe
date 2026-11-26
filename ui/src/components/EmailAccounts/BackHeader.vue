<template>
	<div class="flex shrink-0 items-center justify-between gap-4">
		<div class="flex min-w-0 items-center gap-2">
			<h2 class="min-w-0">
				<Button
					ref="back"
					variant="ghost"
					size="md"
					:disabled="disabled"
					class="-ms-4 text-ink-gray-7 text-md-semibold hover:bg-transparent enabled:hover:opacity-70 active:bg-transparent active:text-ink-gray-5 active:outline-none active:ring-0 active:ring-offset-0 disabled:text-ink-gray-4 pe-0 max-w-96 [justify-content:start]"
					@click="goBack"
				>
					<template #prefix>
						<span class="flex shrink-0 items-center gap-2">
							<span
								class="lucide-chevron-left size-4.5 rtl:rotate-180"
								aria-hidden="true"
							/>
							<slot name="icon" />
						</span>
					</template>
					<span class="sr-only">{{ __("Back:") }}</span>
					{{ title }}
				</Button>
			</h2>
			<Badge v-if="dirty" variant="subtle" theme="amber" size="sm" :label="__('Unsaved')" />
		</div>
		<div v-if="$slots.actions" class="flex shrink-0 items-center gap-2">
			<slot name="actions" />
		</div>
	</div>
</template>

<script setup lang="ts">
import { Badge, Button } from "frappe-ui";
import { onMounted, ref } from "vue";
import { translate as __ } from "../../utils/translate";
import { confirmDiscard } from "./confirmDiscard";

const props = defineProps<{
	/** The screen's title, which is also the back button's label. */
	title: string;
	/** Shows an Unsaved badge, and going back asks to confirm first. */
	dirty?: boolean;
	/** Disables the back button, e.g. while the screen saves. */
	disabled?: boolean;
}>();
const emit = defineEmits<{ back: [] }>();
const back = ref<{ $el: HTMLElement }>();
function focus() {
	back.value?.$el.focus();
}

function goBack() {
	if (!props.dirty) return emit("back");
	confirmDiscard(
		__("Are you sure you want to go back? Unsaved changes will be lost."),
		() => emit("back"),
		focus
	);
}
onMounted(focus);
defineExpose({ focus });
</script>
