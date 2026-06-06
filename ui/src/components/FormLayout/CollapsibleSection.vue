<template>
	<div>
		<slot name="header" v-bind="{ opened, hide, open, close, toggle }">
			<div
				v-if="!hide"
				class="section-header flex items-center justify-between"
				:class="headerClass"
			>
				<div
					class="flex text-ink-gray-9 max-w-fit cursor-pointer items-center gap-2 text-base"
					:class="labelClass"
					@click="collapsible && toggle()"
				>
					<span
						v-if="collapsible && collapseIconPosition === 'left'"
						class="lucide-chevron-right size-4 transition-all duration-300 ease-in-out"
						:class="{ 'rotate-90': opened }"
						aria-hidden="true"
					/>
					<span>{{ label || "Untitled" }}</span>
					<span
						v-if="collapsible && collapseIconPosition === 'right'"
						class="lucide-chevron-right size-4 transition-all duration-300 ease-in-out"
						:class="{ 'rotate-90': opened }"
						aria-hidden="true"
					/>
				</div>
				<slot name="actions"></slot>
			</div>
		</slot>
		<transition
			enter-active-class="duration-300 ease-in"
			leave-active-class="duration-300 ease-[cubic-bezier(0, 1, 0.5, 1)]"
			enter-to-class="max-h-[200px] overflow-hidden"
			leave-from-class="max-h-[200px] overflow-hidden"
			enter-from-class="max-h-0 overflow-hidden"
			leave-to-class="max-h-0 overflow-hidden"
		>
			<div v-show="opened" class="columns" v-bind="$attrs">
				<slot v-bind="{ opened, open, close, toggle }" />
			</div>
		</transition>
	</div>
</template>

<script setup lang="ts">
import { ref } from "vue";

const props = withDefaults(
	defineProps<{
		label?: string;
		hideLabel?: boolean;
		opened?: boolean;
		collapsible?: boolean;
		collapseIconPosition?: "left" | "right";
		labelClass?: string | object | unknown[];
		headerClass?: string | object | unknown[];
	}>(),
	{
		label: "",
		hideLabel: false,
		opened: true,
		collapsible: true,
		collapseIconPosition: "left",
		labelClass: "",
		headerClass: "",
	}
);

const hide = ref(props.hideLabel);
const opened = ref(props.opened);

function toggle() {
	opened.value = !opened.value;
}
function open() {
	opened.value = true;
}
function close() {
	opened.value = false;
}
</script>

<script lang="ts">
export default {
	inheritAttrs: false,
};
</script>
