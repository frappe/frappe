<script setup>
import { watch, ref, nextTick } from "vue";
import { useStore } from "../store";

let props = defineProps(["field"]);
let store = useStore();

let label_input = ref(null);
let editing = ref(false);
let hovered = ref(false);

watch(
	editing,
	value => {
		if (value && !props.field.remove) {
			nextTick(() => label_input.value.focus());
			store.selected_field = props.field.df;
		} else {
			store.selected_field = null;
		}
	},
	{ deep: true }
);
</script>

<template>
	<div
		:class="[
			'field',
			hovered ? 'hovered' : '',
			store.selected(field.df.name) ? 'selected' : ''
		]"
		v-if="!field.remove"
		:title="field.df.fieldname"
		@click.stop="editing = true"
		@mouseover.stop="hovered = true"
		@mouseout.stop="hovered = false"
	>
		<div class="field-controls">
			<div>
				<input
					v-if="editing"
					ref="label_input"
					class="label-input"
					type="text"
					:placeholder="__('Label')"
					v-model="field.df.label"
					@keydown.enter="editing = false"
					@blur="editing = false"
				/>
				<span v-else-if="field.df.label">{{ field.df.label }}</span>
				<i class="text-muted" v-else> {{ __("No Label") }} ({{ field.df.fieldtype }}) </i>
			</div>
			<div class="field-actions">
				<button
					v-if="field.df.fieldtype == 'HTML'"
					class="btn btn-xs btn-icon"
					@click="edit_html"
				>
					<svg class="icon icon-sm">
						<use href="#icon-edit"></use>
					</svg>
				</button>
				<button class="btn btn-xs btn-icon" @click="field.remove = true">
					<svg class="icon icon-sm">
						<use href="#icon-close"></use>
					</svg>
				</button>
			</div>
		</div>
		<div
			v-if="field.df.fieldtype == 'Table'"
			class="table-controls row no-gutters"
			:style="{ opacity: 1 }"
		>
			<div
				class="table-column"
				:style="{ width: tf.width + '%' }"
				v-for="tf in field.table_columns"
				:key="tf.fieldname"
			>
				<div class="table-field">
					{{ tf.label }}
				</div>
			</div>
		</div>
	</div>
</template>

<style lang="scss" scoped>
.field {
	text-align: left;
	width: 100%;
	background-color: var(--bg-light-gray);
	border-radius: var(--border-radius);
	border: 1px solid var(--gray-400);
	padding: 0.5rem 0.75rem;
	font-size: var(--text-sm);

	&:not(:first-child) {
		margin-top: 0.5rem;
	}

	&:focus-within {
		border-style: solid;
		border-color: var(--gray-600);
	}

	&.hovered,
	&.selected {
		border-color: var(--primary);
		.btn.btn-icon {
			opacity: 1 !important;
		}
	}

	.field-controls {
		display: flex;
		justify-content: space-between;
		align-items: center;

		.label-input {
			background-color: transparent;
			border: none;
			padding: 0;

			&:focus {
				outline: none;
			}
		}

		.field-actions {
			flex: none;

			.btn.btn-icon {
				opacity: 0;
				box-shadow: none;
				padding: 2px;

				&:hover {
					background-color: white;
				}
			}
		}
	}

	.table-controls {
		display: flex;
		margin-top: 1rem;

		.table-column {
			position: relative;

			.table-field {
				text-align: left;
				width: 100%;
				background-color: white;
				border-radius: var(--border-radius);
				border: 1px dashed var(--gray-400);
				padding: 0.5rem 0.75rem;
				font-size: var(--text-sm);
				user-select: none;
				white-space: nowrap;
				overflow: hidden;
			}
		}
	}
}
</style>
