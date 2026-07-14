<template>
	<div>
		<div class="total-bar-wrapper mb-3">
			<div class="total-bar-header">
				<span class="text-muted" style="font-size: var(--text-sm)">
					{{ __("Total width used") }}
				</span>
				<span class="es-badge" :data-theme="total_width > 100 ? 'red' : 'green'">
					{{ total_width }}%
				</span>
			</div>
			<div class="total-bar-track">
				<div
					class="total-bar-fill"
					:class="{ 'total-bar-fill--over': total_width > 100 }"
					:style="{ width: Math.min(total_width, 100) + '%' }"
				></div>
			</div>
			<p v-if="total_width > 100" class="text-danger mt-1" style="font-size: var(--text-xs)">
				{{ __("Total exceeds 100%. Columns in red will be removed on save.") }}
			</p>
		</div>

		<div class="columns-header row font-weight-bold mb-1">
			<div class="col-8">{{ __("Column") }}</div>
			<div class="col-4 text-right pr-4">{{ __("Width %") }}</div>
		</div>

		<draggable
			:list="df.table_columns"
			:animation="200"
			:group="df.fieldname"
			handle=".icon-drag"
		>
			<template #item="{ element: column }">
				<div class="column-row row align-items-center mt-2">
					<div class="col-8">
						<div class="column-label-row">
							<div class="icon-drag" v-html="frappe.utils.icon('grip', 'xs')"></div>
							<input
								class="input-column-label"
								:class="{ 'text-danger': column.invalid_width }"
								type="text"
								v-model="column.label"
								:placeholder="column.fieldname"
							/>
						</div>
					</div>
					<div class="col-4 d-flex align-items-center gap-2">
						<div
							class="width-input-wrap"
							:class="{ 'width-input-wrap--invalid': column.invalid_width }"
						>
							<input
								type="number"
								class="width-input"
								v-model.number="column.width"
								min="0"
								max="100"
								step="5"
							/>
							<span class="width-suffix">%</span>
						</div>
						<button
							class="es-button"
							data-size="xs"
							data-variant="ghost"
							data-icon-button="true"
							:title="__('Remove column')"
							@click="remove_column(column)"
							v-html="frappe.utils.icon('x', 'xs')"
						></button>
					</div>
				</div>
			</template>
		</draggable>
	</div>
</template>

<script setup>
import { computed } from "vue";
import draggable from "vuedraggable";

const props = defineProps(["df"]);

function remove_column(column) {
	props.df["table_columns"] = props.df.table_columns.filter((_column) => _column !== column);
}

let total_width = computed(() => {
	return props.df.table_columns.reduce((total, tf) => total + (tf.width || 0), 0);
});
</script>

<style scoped>
/* Total bar */
.total-bar-wrapper {
	background: var(--bg-light-gray);
	border-radius: var(--radius);
	padding: 0.6rem 0.75rem;
}
.total-bar-header {
	display: flex;
	justify-content: space-between;
	align-items: center;
	margin-bottom: 0.4rem;
}
.total-bar-track {
	height: 6px;
	background: var(--gray-200);
	border-radius: var(--radius-full);
	overflow: hidden;
}
.total-bar-fill {
	height: 100%;
	background: var(--green-400);
	border-radius: var(--radius-full);
	transition: width 0.2s ease, background 0.2s ease;
}
.total-bar-fill--over {
	background: var(--red-400);
}

/* Header */
.columns-header {
	font-size: var(--text-sm);
	color: var(--text-muted);
	padding: 0 0.25rem;
}

/* Column row */
.column-row {
	border-radius: var(--radius);
	padding: 0.25rem 0;
}
.column-label-row {
	display: flex;
	align-items: center;
	gap: 0.25rem;
}
.icon-drag {
	cursor: grab;
	color: var(--gray-400);
	display: flex;
	align-items: center;
	flex-shrink: 0;
}
.icon-drag:hover {
	color: var(--gray-600);
}
.input-column-label {
	border: 1px solid transparent;
	border-radius: var(--radius);
	font-size: var(--text-md);
	background: transparent;
	padding: 2px 4px;
	flex: 1;
	min-width: 0;
}
.input-column-label:hover {
	border-color: var(--gray-300);
}
.input-column-label:focus {
	border-color: var(--border-color);
	outline: none;
	background-color: var(--control-bg);
}

/* Width input */
.width-input-wrap {
	display: flex;
	align-items: center;
	border: 1px solid var(--gray-300);
	border-radius: var(--radius);
	background: var(--fg-color);
	overflow: hidden;
	flex: 1;
}
.width-input-wrap--invalid {
	border-color: var(--red-400);
	background: var(--red-50);
}
.width-input {
	border: none;
	outline: none;
	background: transparent;
	text-align: right;
	padding: 4px 4px 4px 8px;
	width: 100%;
	font-size: var(--text-sm);
	color: inherit;
}
.width-input-wrap--invalid .width-input {
	color: var(--red-600);
}
.width-suffix {
	padding: 4px 6px 4px 2px;
	font-size: var(--text-sm);
	color: var(--text-muted);
	white-space: nowrap;
}
.width-input-wrap--invalid .width-suffix {
	color: var(--red-400);
}

.gap-2 {
	gap: 0.5rem;
}
</style>
