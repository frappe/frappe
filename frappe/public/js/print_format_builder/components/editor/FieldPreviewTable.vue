<template>
	<div v-if="df.label && df.show_label !== 'hide'" class="label">
		{{ df.label }}
	</div>
	<table
		class="table"
		:style="{
			...(df.table_radius != null ? { '--pfb-radius': df.table_radius + 'px' } : {}),
			...(df.table_header_bg && df.table_header !== 'plain'
				? { '--pfb-header-bg': df.table_header_bg }
				: {}),
		}"
	>
		<thead v-if="df.table_header !== 'none'">
			<tr>
				<th
					v-for="(col, ci) in df.table_columns"
					:key="col.fieldname"
					class="column-header"
					:class="{ 'column-value--merged': has_merge(col) }"
					:data-fieldtype="col.fieldtype"
					:data-fieldname="col.fieldname"
					:style="(col.width ? `width: ${col.width}%; ` : '') + cell_style(df)"
				>
					{{ col.label || col.fieldname }}
					<span
						v-if="ci < df.table_columns.length - 1"
						class="col-resize-handle"
						@pointerdown.prevent.stop="start_col_resize($event, ci)"
						@mousedown.prevent.stop
						@click.stop
					></span>
				</th>
			</tr>
		</thead>
		<tbody>
			<tr
				v-for="(row, i) in (preview_doc[df.fieldname] || []).slice(0, 4)"
				:key="i"
				:class="i % 2 === 0 ? 'odd' : 'even'"
			>
				<td
					v-for="col in df.table_columns"
					:key="col.fieldname"
					class="column-value"
					:class="{ 'column-value--merged': has_merge(col) }"
					:data-fieldtype="col.fieldtype"
					:data-fieldname="col.fieldname"
					:style="(col.width ? `width: ${col.width}%; ` : '') + cell_style(df)"
				>
					<!-- Merged cell: image (if any) floats left, text lines stack -->
					<div v-if="has_merge(col)" class="cell-merged">
						<template v-if="image_merge(col)">
							<img
								v-if="cell_image(col, row)"
								:src="cell_image(col, row)"
								class="cell-thumb-img"
								:style="thumb_box(col)"
								:alt="col.label || col.fieldname"
							/>
							<span v-else class="cell-thumb" :style="thumb(col, row).style">{{
								thumb(col, row).abbr
							}}</span>
						</template>
						<div
							class="cell-lines"
							:class="{
								'cell-lines--horizontal': col.merge_direction === 'horizontal',
							}"
						>
							<div
								v-for="(mf, mi) in text_merges(col)"
								:key="mi"
								class="cell-line"
								:class="`cell-line--${mf.style || 'primary'}`"
							>
								{{ format_merged(row, i, mf.fieldname) }}
							</div>
						</div>
					</div>
					<!-- Single (default) -->
					<template v-else>
						<img
							v-if="is_image_field(col, row[col.fieldname]) && row[col.fieldname]"
							:src="row[col.fieldname]"
							class="preview-table-img"
							:alt="col.label || col.fieldname"
						/>
						<div
							v-else-if="cell_server_html(i, col)"
							class="preview-table-html"
							v-html="cell_server_html(i, col)"
						></div>
						<span v-else>{{ format_cell(row, col) }}</span>
					</template>
				</td>
			</tr>
		</tbody>
		<!-- after tbody (HTML5 order): user styles that remap tfoot's display can
		     no longer float the cap up under the header -->
		<tfoot>
			<tr>
				<td v-for="i in df.table_columns?.length || 1" :key="i" class="table-foot"></td>
			</tr>
		</tfoot>
	</table>
	<!-- outside the table: a note row inside tbody would take over `tr:last-child`,
	     which every last-row border rule is keyed on -->
	<div v-if="!preview_doc[df.fieldname]?.length" class="text-muted pfb-table-note">
		{{ __("No rows") }}
	</div>
	<div v-else-if="preview_doc[df.fieldname].length > 4" class="text-muted pfb-table-note">
		{{
			__("+ {0} more rows in this document — all print in the real output", [
				preview_doc[df.fieldname].length - 4,
			])
		}}
	</div>
</template>

<script setup>
import { computed, inject } from "vue";
import { useColumnResize } from "../../composables/useColumnResize";
import { useFieldFormat } from "../../composables/useFieldFormat";

const props = defineProps(["df"]);
const store = inject("$store");
const preview_doc = computed(() => store.preview_doc.value);

const {
	cell_style,
	is_image_field,
	cell_server_html,
	format_cell,
	has_merge,
	image_merge,
	text_merges,
	format_merged,
	cell_image,
	thumb_box,
	thumb,
} = useFieldFormat(props, store, preview_doc);

const { start: start_column_resize } = useColumnResize();

function start_col_resize(e, ci) {
	const cols = props.df.table_columns;
	const left = cols[ci];
	const right = cols[ci + 1];
	if (!right) return;
	const table_width = e.target.closest("table").getBoundingClientRect().width;
	const start_x = e.clientX;
	const start_left = left.width || 10;
	const start_right = right.width || 10;
	const on_move = (ev) => {
		let delta = Math.round(((ev.clientX - start_x) / table_width) * 100);
		delta = Math.max(5 - start_left, Math.min(start_right - 5, delta));
		left.width = start_left + delta;
		right.width = start_right - delta;
	};
	start_column_resize(e.target, "col-resize-handle--active", on_move);
}
</script>

<style>
body.pfb-col-resizing,
body.pfb-col-resizing * {
	cursor: col-resize !important;
	user-select: none;
}
</style>

<style scoped>
.column-header {
	position: relative;
}

.col-resize-handle {
	position: absolute;
	top: 0;
	bottom: 0;
	right: -4px;
	width: 8px;
	cursor: col-resize;
	z-index: 1;
}

.col-resize-handle::after {
	content: "";
	position: absolute;
	top: 2px;
	bottom: 2px;
	left: 3px;
	width: 2px;
	border-radius: 1px;
	background: var(--gray-400);
	opacity: 0;
	transition: opacity 0.15s;
}

thead:hover .col-resize-handle::after {
	opacity: 0.4;
}

.col-resize-handle:hover::after,
.col-resize-handle--active::after {
	opacity: 1;
}

.preview-table-img {
	max-width: 100%;
	max-height: 100px;
}

.preview-table-html {
	word-break: break-word;
	white-space: normal;
}
</style>
