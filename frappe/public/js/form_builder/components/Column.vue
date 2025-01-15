<template>
	<div
		:class="['column', selected ? 'selected' : hovered ? 'hovered' : '']"
		:title="column.df.fieldname"
		@click.stop="store.form.selected_field = column.df"
		@mouseover.stop="hovered = true"
		@mouseout.stop="hovered = false"
	>
		<div
			v-if="column.df.label"
			class="column-header"
			:hidden="!column.df.label && store.read_only"
		>
			<div class="column-label">
				<span>{{ __(column.df.label) }}</span>
			</div>
		</div>
		<div v-if="column.df.description" class="column-description">
			{{ __(column.df.description) }}
		</div>
		<draggable
			class="column-container"
			v-model="column.fields"
			group="fields"
			:delay="is_touch_screen_device() ? 200 : 0"
			:animation="200"
			:easing="store.get_animation"
			item-key="id"
			:disabled="store.read_only"
		>
			<template #item="{ element }">
				<Field
					:column="column"
					:field="element"
					:data-is-user-generated="store.is_user_generated_field(element)"
				/>
			</template>
		</draggable>
		<div class="empty-column" :hidden="store.read_only">
			<AddFieldButton :column="column" />
		</div>
		<div v-if="column.fields.length" class="add-new-field-btn">
			<AddFieldButton :field="column.fields[column.fields.length - 1]" :column="column" />
		</div>
	</div>
</template>

<script setup>
import draggable from "vuedraggable";
import Field from "./Field.vue";
import AddFieldButton from "./AddFieldButton.vue";
import { computed, ref } from "vue";
import { useStore } from "../store";
import { is_touch_screen_device } from "../utils";
import { useMagicKeys, whenever } from "@vueuse/core";

const props = defineProps(["section", "column"]);
const store = useStore();

// delete/backspace to delete the field
const { Backspace } = useMagicKeys();
whenever(Backspace, (value) => {
	if (value && selected.value && store.not_using_input) {
		remove_column();
	}
});

const hovered = ref(false);
const selected = computed(() => store.selected(props.column.df.name));
</script>

<style lang="scss" scoped>
.column {
	position: relative;
	display: flex;
	flex-direction: column;
	width: 100%;
	background-color: var(--bg-light-gray);
	border-radius: var(--border-radius);
	border: 1px dashed var(--gray-400);
	padding: 0.5rem;
	margin-left: 4px;
	margin-right: 4px;

	&.hovered,
	&.selected {
		border-color: var(--border-primary);
		border-style: solid;
	}

	.column-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding-bottom: 0.5rem;
		padding-left: 0.3rem;

		.column-label {
			:deep(span) {
				font-weight: 600;
				color: var(--heading-color);
			}
		}

		.column-actions {
			display: flex;
			justify-content: flex-end;

			.btn.btn-icon {
				padding: 2px;
				box-shadow: none;
				opacity: 0;

				&:hover {
					opacity: 1;
					background-color: var(--fg-color);
				}
			}
		}
	}

	.column-description {
		margin-bottom: 10px;
		margin-left: 0.3rem;
		font-size: var(--text-xs);
		color: var(--text-muted);
	}

	&:first-child {
		margin-left: 0px;
	}

	&:last-child {
		margin-right: 0px;
	}

	.column-container {
		min-height: 2rem;
		border-radius: var(--border-radius);
		z-index: 1;

		&:empty {
			flex: 1;
			& + .empty-column {
				display: flex;
				justify-content: center;
				flex-direction: column;
				align-items: center;
				position: absolute;
				top: 0;
				bottom: 0;
				left: 0;
				gap: 5px;
				width: 100%;
				padding: 15px;

				button {
					background-color: var(--bg-color);
					z-index: 2;

					&:hover {
						background-color: var(--btn-default-hover-bg);
					}
				}
			}
		}

		& + .empty-column {
			display: none;
		}
	}

	.add-new-field-btn {
		padding: 10px 6px 5px;

		button {
			background-color: var(--fg-color);

			&:hover {
				background-color: var(--btn-default-hover-bg);
			}
		}
	}
}
</style>
