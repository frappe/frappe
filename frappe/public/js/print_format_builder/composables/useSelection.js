import { ref, watch, computed } from "vue";

export function useSelection() {
	const selected_field = ref(null);
	const selected_fields = ref([]);
	const selected_section = ref(null);
	const selected_sections = ref([]);
	const selected_letterhead = ref(false);
	const selected_lh_footer = ref(false);

	// more than one field/section selected — the single source of truth for
	// "bulk mode" (bulk panel, and hiding per-item toolbars on the canvas)
	const is_multi_select = computed(
		() => selected_fields.value.length + selected_sections.value.length > 1
	);

	function select_field(df, additive = false) {
		if (additive && df) {
			const arr = selected_fields.value.slice();
			const i = arr.indexOf(df);
			if (i === -1) arr.push(df);
			else arr.splice(i, 1);
			selected_fields.value = arr;
			selected_field.value = arr[arr.length - 1] || null;
		} else {
			selected_fields.value = df ? [df] : [];
			selected_field.value = df;
		}
		// selecting a field drops any section selection (symmetric with select_section)
		selected_section.value = null;
		selected_sections.value = [];
		selected_letterhead.value = false;
		selected_lh_footer.value = false;
	}
	// fields-only setter (used by shift-range)
	function set_selected(fields) {
		set_selection({ fields });
	}
	// unified setter — marquee can select any mix of fields and sections
	function set_selection({ fields = [], sections = [] }) {
		selected_fields.value = fields.slice();
		selected_field.value = fields[fields.length - 1] || null;
		selected_sections.value = sections.slice();
		selected_section.value = sections[sections.length - 1] || null;
		selected_letterhead.value = false;
		selected_lh_footer.value = false;
	}
	watch(selected_field, (nf) => {
		if (!nf) {
			if (selected_fields.value.length) selected_fields.value = [];
		} else if (!selected_fields.value.includes(nf)) {
			selected_fields.value = [nf];
		}
	});
	watch(selected_section, (ns) => {
		if (!ns) {
			if (selected_sections.value.length) selected_sections.value = [];
		} else if (!selected_sections.value.includes(ns)) {
			selected_sections.value = [ns];
		}
	});
	function remove_field(df) {
		df.remove = true;
		const rest = selected_fields.value.filter((f) => f !== df);
		if (rest.length !== selected_fields.value.length) selected_fields.value = rest;
		if (selected_field.value === df) selected_field.value = rest[rest.length - 1] || null;
	}
	function align_selected_fields(align) {
		selected_fields.value.forEach((df) => (df.align = align));
	}
	function select_section(section) {
		selected_section.value = section;
		selected_sections.value = section ? [section] : [];
		selected_field.value = null;
		selected_fields.value = [];
		selected_letterhead.value = false;
		selected_lh_footer.value = false;
	}
	function select_letterhead({ footer = false } = {}) {
		selected_letterhead.value = !footer;
		selected_lh_footer.value = footer;
		selected_field.value = null;
		selected_section.value = null;
	}

	return {
		selected_field,
		selected_fields,
		selected_section,
		selected_sections,
		selected_letterhead,
		selected_lh_footer,
		is_multi_select,
		select_field,
		set_selected,
		set_selection,
		select_section,
		select_letterhead,
		remove_field,
		align_selected_fields,
	};
}
