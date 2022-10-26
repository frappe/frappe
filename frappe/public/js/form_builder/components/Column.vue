<script setup>
import draggable from "vuedraggable";
import Field from "./Field.vue";
import { ref } from "vue";
import { useStore } from "../store";

let props = defineProps(["column"]);
let store = useStore();

let hovered = ref(false);
</script>

<template>
	<div
		:class="[
			'column',
			hovered ? 'hovered' : '',
			store.selected(column.df.name) ? 'selected' : ''
		]"
		:title="column.df.fieldname"
		@click.stop="store.selected_field = column.df"
		@mouseover.stop="hovered = true"
		@mouseout.stop="hovered = false"
	>
		<draggable
			class="column-container"
			:style="{
				backgroundColor: column.fields.length ? null : 'var(--gray-50)'
			}"
			v-model="column.fields"
			group="fields"
			filter="[data-is-custom='0']"
			:animation="150"
			item-key="id"
			:disabled="store.read_only"
		>
			<template #item="{ element }">
				<Field
					:field="element"
					:data-is-custom="store.is_custom(element)"
				/>
			</template>
		</draggable>
	</div>
</template>

<style lang="scss" scoped>
.column {
	width: 100%;
	background-color: var(--bg-light-gray);
	border-radius: var(--border-radius);
	border: 1px solid var(--gray-400);
	padding: 0.5rem;
	margin-left: 4px;
	margin-right: 4px;

	&.hovered,
	&.selected {
		border-color: var(--primary);
		.btn.btn-icon {
			opacity: 1 !important;
		}
	}

	&.selected {
		.column-actions {
			display: flex !important;
		}

		.column-container {
			height: 80%;
		}
	}

	&:first-child {
		margin-left: 0px;
	}

	&:last-child {
		margin-right: 0px;
	}

	.column-container {
		height: 100%;
		min-height: 2rem;
		border-radius: var(--border-radius);
	}
}
</style>
