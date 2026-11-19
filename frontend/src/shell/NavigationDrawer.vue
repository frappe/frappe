<!-- A panel from the navigation's side, at most 85vw, over a 30% scrim. -->
<template>
	<Transition
		enter-active-class="transition-opacity duration-200 motion-reduce:transition-none"
		leave-active-class="transition-opacity duration-200 motion-reduce:transition-none"
		enter-from-class="opacity-0"
		leave-to-class="opacity-0"
	>
		<div
			v-if="open"
			data-navigation-drawer-scrim
			class="fixed inset-0 z-40 bg-black/30"
			@click="close"
		/>
	</Transition>

	<Transition
		enter-active-class="transition-transform duration-200 ease-out motion-reduce:transition-none"
		leave-active-class="transition-transform duration-200 ease-in motion-reduce:transition-none"
		:enter-from-class="away"
		:leave-to-class="away"
		@after-enter="panel?.focus()"
	>
		<div
			v-if="open"
			ref="panel"
			role="dialog"
			aria-modal="true"
			:aria-label="__('Navigation')"
			tabindex="-1"
			data-navigation-drawer
			class="fixed inset-y-0 z-50 flex w-fit max-w-[85vw] overflow-hidden bg-surface-base shadow-2xl focus:outline-none"
			:class="[
				navSide() === 'left' ? 'left-0' : 'right-0',
				// The rail on the outer edge, as DesktopShell draws it.
				navSide() === 'right' ? 'flex-row-reverse rtl:flex-row' : 'rtl:flex-row-reverse',
			]"
			@click="onClick"
			@keydown.tab="trap"
		>
			<slot />
		</div>
	</Transition>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { useEventListener } from "@vueuse/core";
import { __ } from "@/i18n";
import { navSide } from "./navigationSide";

const props = defineProps<{
	open: boolean;
	/** The page has a sidebar: a rail cell that opened it was browsing, so the drawer stays. */
	hasSidebar: boolean;
}>();
const emit = defineEmits<{ close: [] }>();

const route = useRoute();
const panel = ref<HTMLElement | null>(null);
const away = computed(() => (navSide() === "left" ? "-translate-x-full" : "translate-x-full"));

function close() {
	emit("close");
}

let browsing = false;

function onClick(event: MouseEvent) {
	const target = event.target instanceof Element ? event.target : null;
	const cell = target?.closest('[data-slot="sidebar-rail-item"]');
	browsing = !!cell?.closest("[data-sidebar]");
	if (cell) {
		if (!browsing) close();
		return;
	}
	if (target?.closest('[data-slot="sidebar-item"], a[href], button[aria-busy]')) close();
}

watch(
	() => route.path,
	() => {
		const stay = browsing && props.hasSidebar;
		browsing = false;
		if (!stay) close();
	},
	{ flush: "post" }
);

useEventListener(window, "keydown", (event: KeyboardEvent) => {
	if (props.open && event.key === "Escape" && !event.defaultPrevented) close();
});

const FOCUSABLE =
	'a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])';

function trap(event: KeyboardEvent) {
	const nodes = [...(panel.value?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? [])].filter(
		(node) => node.checkVisibility?.() !== false
	);
	if (!nodes.length) return event.preventDefault();
	const first = nodes[0];
	const last = nodes[nodes.length - 1];
	const active = document.activeElement;
	if (event.shiftKey && (active === first || active === panel.value)) {
		event.preventDefault();
		last.focus();
	} else if (!event.shiftKey && active === last) {
		event.preventDefault();
		first.focus();
	}
}

// A resize unmounts the open drawer with its button: focus must not fall to the body.
onBeforeUnmount(() => {
	if (props.open && panel.value?.contains(document.activeElement)) {
		void nextTick(() => document.querySelector<HTMLElement>("main")?.focus());
	}
});

let opener: Element | null = null;
watch(
	() => props.open,
	async (open) => {
		if (open) {
			opener = document.activeElement;
			return;
		}
		browsing = false;
		await nextTick();
		if (opener instanceof HTMLElement) opener.focus();
	}
);
</script>
