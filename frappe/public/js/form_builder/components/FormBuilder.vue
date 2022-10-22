<script setup>
import Sidebar from "./Sidebar.vue";
import Tabs from "./Tabs.vue";
import { computed, onMounted, watch } from "vue";
import { useStore } from "../store";

let store = useStore();

let should_render = computed(() => {
	return Object.keys(store.layout).length !== 0;
});

watch(
	() => store.layout,
	() => (store.dirty = true),
	{ deep: true }
);

onMounted(() => store.fetch());
</script>

<template>
	<div class="form-builder-container" v-if="should_render">
		<div class="form-controls">
			<div class="form-sidebar">
				<Sidebar />
			</div>
		</div>
		<div class="form-container">
			<div class="form-main">
				<Tabs />
			</div>
		</div>
	</div>
</template>

<style lang="scss" scoped>
.form-builder-container {
	margin-bottom: -60px;
	display: flex;
	gap: 20px;

	&.resizing {
		user-select: none;
		cursor: col-resize;
	}

	.form-controls {
		position: relative;
	}

	.form-container {
		flex: 1;
	}

	.form-sidebar,
	.form-main {
		border-radius: var(--border-radius);
		box-shadow: var(--card-shadow);
		background-color: var(--card-bg);

		:deep(.column-container .field.sortable-chosen) {
			background-color: var(--bg-light-gray);
			border-radius: var(--border-radius);
			border: 1px dashed var(--gray-400);
			padding: 0.5rem 0.75rem;
			font-size: var(--text-sm);
			cursor: pointer;

			&:not(:first-child) {
				margin-top: 0.5rem;
			}
		}

		:deep([data-is-custom="1"]) {
			background-color: var(--yellow-highlight-color);
		}
	}
}
</style>
