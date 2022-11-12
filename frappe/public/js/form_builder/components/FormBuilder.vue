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

function lose_focus() {
	store.selected_field = null;
}

onMounted(() => store.fetch());
</script>

<template>
	<div
		class="form-builder-container"
		v-if="should_render"
		v-on-outside-click="lose_focus"
		@click="lose_focus"
	>
		<div class="form-controls" @click.stop>
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
			border-radius: var(--border-radius-sm);
			border: 1px solid transparent;
			padding: 0.3rem;
			font-size: var(--text-sm);
			cursor: pointer;

			&:has(.drag-it-here) {
				position: relative;
				background-color: transparent;
				height: 60px;

				.drag-it-here {
					display: flex;
					justify-content: center;

					&::after {
						content: "Drag it here";
						top: 31%;
						position: absolute;
						padding: 2px 10px;
						color: var(--fg-color);
						background-color: var(--gray-500);
						border-radius: var(--border-radius-full);
						z-index: 1;
					}
					&::before {
						content: "";
						top: 47%;
						position: absolute;
						width: 97%;
						height: 4px;
						background-color: var(--gray-500);
						border-radius: var(--border-radius-full);
					}
				}
			}

			&:not(:first-child) {
				margin-top: 0.4rem;
			}
		}

		:deep(.field) {
			.description {
				font-size: var(--text-sm);
				color: var(--text-muted);
			}

			.reqd::after {
				content: " *";
				color: var(--red-400);
			}
		}

		:deep([data-has-std-field="false"]),
		:deep([data-is-custom="1"]) {
			background-color: var(--yellow-highlight-color);
		}
	}

	.form-main:not(:has(.tab-header)) :deep(.tab-contents) {
		max-height: calc(100vh - 160px);
	}
}
</style>
