<template>
	<Teleport to="body">
		<div v-if="state.visible" ref="menu" class="pfb-context-menu" :style="menu_style">
			<template v-for="(item, i) in state.items" :key="i">
				<div v-if="item.divider" class="pfb-context-divider"></div>
				<button
					v-else
					class="pfb-context-item"
					:class="{ 'is-danger': item.danger }"
					@click="run(item)"
				>
					<span
						v-if="item.icon"
						class="pfb-context-icon"
						v-html="frappe.utils.icon(item.icon, 'sm')"
					></span>
					<span class="pfb-context-label">{{ item.label }}</span>
				</button>
			</template>
		</div>
	</Teleport>
</template>

<script setup>
import { onBeforeUnmount, ref, watch, nextTick } from "vue";
import { useContextMenu } from "../../composables/useContextMenu";

const { state, close } = useContextMenu();
const menu = ref(null);
const menu_style = ref({});

function run(item) {
	close();
	item.action?.();
}

function on_key(e) {
	if (e.key === "Escape") close();
}
function on_doc_down(e) {
	if (menu.value && !menu.value.contains(e.target)) close();
}
function on_scroll() {
	close();
}

function arm() {
	document.addEventListener("pointerdown", on_doc_down, true);
	window.addEventListener("keydown", on_key);
	window.addEventListener("scroll", on_scroll, true);
}
function disarm() {
	document.removeEventListener("pointerdown", on_doc_down, true);
	window.removeEventListener("keydown", on_key);
	window.removeEventListener("scroll", on_scroll, true);
}

watch(
	() => state.visible,
	(visible) => {
		if (!visible) return disarm();
		// render off-screen first so we can measure and clamp to the viewport
		menu_style.value = { left: `${state.x}px`, top: `${state.y}px`, visibility: "hidden" };
		nextTick(() => {
			const el = menu.value;
			if (!el) return;
			const { width, height } = el.getBoundingClientRect();
			const pad = 8;
			let left = state.x;
			let top = state.y;
			if (left + width + pad > window.innerWidth) left = window.innerWidth - width - pad;
			if (top + height + pad > window.innerHeight) top = window.innerHeight - height - pad;
			menu_style.value = {
				left: `${Math.max(pad, left)}px`,
				top: `${Math.max(pad, top)}px`,
			};
			// arm on the next tick so the click that opened the menu can't close it
			arm();
		});
	}
);

onBeforeUnmount(disarm);
</script>

<style scoped>
.pfb-context-menu {
	position: fixed;
	z-index: 1050;
	min-width: 180px;
	padding: 4px;
	background: var(--fg-color);
	border: 1px solid var(--border-color);
	border-radius: var(--radius);
	box-shadow: var(--shadow-lg);
	display: flex;
	flex-direction: column;
	gap: 1px;
}

.pfb-context-item {
	display: flex;
	align-items: center;
	gap: 8px;
	width: 100%;
	padding: 5px 8px;
	background: transparent;
	border: none;
	border-radius: var(--radius);
	font-size: var(--text-sm);
	color: var(--text-color);
	text-align: left;
	cursor: pointer;
}

.pfb-context-item:hover {
	background: var(--gray-100);
}

.pfb-context-item.is-danger {
	color: var(--red-500);
}

.pfb-context-item.is-danger:hover {
	background: var(--red-50);
}

.pfb-context-icon {
	display: flex;
	align-items: center;
	color: var(--gray-600);
}

.pfb-context-item.is-danger .pfb-context-icon {
	color: var(--red-500);
}

.pfb-context-divider {
	height: 1px;
	margin: 4px 0;
	background: var(--border-color);
}
</style>
