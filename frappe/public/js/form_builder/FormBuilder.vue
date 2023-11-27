<script setup>
import Sidebar from "./components/Sidebar.vue";
import Tabs from "./components/Tabs.vue";
import { computed, onMounted, watch, ref } from "vue";
import { useStore } from "./store";
import { onClickOutside } from "@vueuse/core";

let store = useStore();

let should_render = computed(() => {
	return Object.keys(store.form.layout).length !== 0;
});

let container = ref(null);
onClickOutside(container, () => (store.form.selected_field = null), {
	ignore: [".combo-box-options"],
});

watch(
	() => store.form.layout,
	() => (store.dirty = true),
	{ deep: true }
);

onMounted(() => store.fetch());
</script>

<template>
	<div
		v-if="should_render"
		ref="container"
		class="form-builder-container"
		@click="store.form.selected_field = null"
	>
		<div class="form-container">
			<div class="form-main" :class="[store.preview ? 'preview' : '']">
				<Tabs />
			</div>
		</div>
		<div class="form-controls" @click.stop>
			<div class="form-sidebar">
				<Sidebar />
			</div>
		</div>
	</div>
	<div id="autocomplete-area" />
</template>

<style lang="scss" scoped>
.form-builder-container {
	margin: -15px -20px -5px;
	display: flex;

	&.resizing {
		user-select: none;
		cursor: col-resize;
	}

	.form-controls {
		position: relative;
	}

	.form-container {
		flex: 1;
		background-color: var(--disabled-control-bg);
	}

	.form-sidebar {
		border-left: 1px solid var(--border-color);
		border-bottom-right-radius: var(--border-radius);
	}

	.form-main {
		border-radius: var(--border-radius);
		border: 1px solid var(--border-color);
		background-color: var(--card-bg);
		margin: 5px;
	}

	.form-sidebar,
	.form-main {
		:deep(.section-columns.has-one-column .field) {
			input.form-control,
			.signature-field {
				width: calc(50% - 19px);
			}

			.select-input {
				width: calc(50% - 19px);

				input.form-control {
					width: 100%;
				}
			}
		}

		:deep(.column-container .field.sortable-chosen) {
			background-color: var(--bg-light-gray);
			border-radius: var(--border-radius-sm);
			border: 1px solid transparent;
			padding: 0.3rem;
			font-size: var(--text-sm);
			cursor: pointer;

			&:not(.hovered) {
				position: relative;
				background-color: transparent;
				height: 60px;

				.drop-it-here {
					display: flex;
					justify-content: center;

					&::after {
						content: "Drop it here";
						top: 31%;
						position: absolute;
						padding: 2px 10px;
						color: var(--text-dark);
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
			.label {
				margin-bottom: 0.3rem;
			}

			.editable {
				input,
				textarea,
				select,
				.ace_editor,
				.ace_gutter,
				.ace_content,
				.signature-field,
				.missing-image,
				.ql-editor {
					background-color: var(--fg-color);
					cursor: pointer;
				}

				.input-text {
					background-color: inherit;
				}
			}

			.description,
			.time-zone {
				font-size: var(--text-sm);
				color: var(--text-muted);
			}
		}

		:deep([data-is-user-generated="1"]) {
			background-color: var(--yellow-highlight-color);
		}
	}

	:deep(.preview) {
		.tab,
		.column,
		.field {
			background-color: var(--fg-color);
		}

		.column,
		.field {
			border: none;
			padding: 0;
		}

		.form-section {
			padding: 5px;

			.section-header {
				&.has-label {
					padding: 10px 15px;
					margin-bottom: 8px;
				}

				&.collapsed {
					margin-bottom: 0;
				}
			}

			.section-description {
				padding-left: 15px;
			}

			.section-columns {
				margin-top: 8px;

				&.has-one-column .field {
					input.form-control,
					.signature-field {
						width: calc(50% - 15px);
					}

					.select-input {
						width: calc(50% - 15px);

						input.form-control {
							width: 100%;
						}
					}
				}

				.section-columns-container {
					.column {
						padding-left: 15px;
						padding-right: 15px;
						margin: 0;

						.column-header {
							padding-left: 0;
						}

						.column-description {
							margin-left: 0;
						}

						.field {
							margin: 0;
							margin-bottom: 1rem;
							.field-controls {
								margin-bottom: 5px;
							}
						}

						.add-new-field-btn {
							display: none;
						}
					}
				}
			}
		}

		.selected,
		.hovered {
			border-color: transparent;
		}

		input,
		textarea,
		select,
		.ace_editor,
		.ace_gutter,
		.ace_content,
		.signature-field,
		.missing-image,
		.ql-editor {
			background-color: var(--control-bg) !important;
		}

		input[type="checkbox"] {
			background-color: var(--fg-bg) !important;
		}
	}

	.form-main > :deep(div:first-child:not(.tab-header)) {
		max-height: calc(100vh - 175px);
	}
}
</style>
