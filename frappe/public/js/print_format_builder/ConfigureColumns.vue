<template>
	<div>
		<p class="text-muted">
			{{ help_message }}
		</p>
		<div class="row font-weight-bold">
			<div class="col-8">
				{{ __("Column") }}
			</div>
			<div class="col-4">
				{{ __("Width") }}
			</div>
		</div>
		<draggable
			:list="df.table_columns"
			:animation="200"
			:group="df.fieldname"
			handle=".icon-drag"
		>
			<div
				class="row mt-2 align-center column-row"
				v-for="column in df.table_columns"
			>
				<div class="col-8">
					<div class="column-label d-flex align-center">
						<div class="icon-drag px-2 ml-n2">
							<svg class="icon icon-xs">
								<use xlink:href="#icon-drag"></use>
							</svg>
						</div>
						<div class="ml-1" :class="{ 'text-danger': column.invalid_width }">
							{{ column.label }}
						</div>
					</div>
				</div>
				<div class="col-4 d-flex align-items-center">
					<input
						type="number"
						class="form-control text-right"
						v-model.number="column.width"
						min="1"
						max="12"
					/>
					<button
						class="btn btn-xs btn-icon ml-2"
						@click="remove_column(column)"
					>
						<svg class="icon icon-sm">
							<use xlink:href="#icon-close"></use>
						</svg>
					</button>
				</div>
			</div>
		</draggable>
	</div>
</template>
<script>
import draggable from "vuedraggable";
export default {
	name: "ConfigureColumns",
	props: ["df"],
	components: {
		draggable
	},
	methods: {
		remove_column(column) {
			this.$set(
				this.df,
				"table_columns",
				this.df.table_columns.filter(_column => _column !== column)
			);
		}
	},
	computed: {
		help_message() {
			// prettier-ignore
			return __("Drag columns to set order. The total width should be 12, columns marked in red will be removed.");
		}
	}
};
</script>
<style scoped>
.icon-drag {
	cursor: grab;
}
</style>
