// What a widget's renderer gets from `useWidget()`, for one tile.

import { computed, inject, ref } from "vue";
import { provideWidget } from "@framework/ui/widget";

export function provide_widget_state({
	widget,
	data,
	loading = ref(false),
	error = ref(null),
	filters = ref({}),
	setFilters = () => {},
	refresh = () => {},
}) {
	const state = {
		widget,
		config: computed(() => widget.value.config || {}),
		data,
		loading,
		error,
		size: inject("tile_size", ref("M")),
		editing: inject("editing", ref(false)),
		filters,
		setFilters,
		refresh,
	};
	provideWidget(state);
	return state;
}

// Old filters are an object or `[doctype, field, op, value]` rows; a widget's are `[field, op, value]`.
export function short_filters(filters, doctype) {
	if (!filters) return [];
	if (!Array.isArray(filters)) {
		return Object.entries(filters).map(([field, value]) =>
			Array.isArray(value) ? [field, ...value] : [field, "=", value]
		);
	}
	return filters.map((row) => (row.length >= 4 && row[0] === doctype ? row.slice(1, 4) : row));
}
