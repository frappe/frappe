import { ref, watch } from "vue";

export function useSelection() {
	const selected_field = ref(null);
	const selected_fields = ref([]);
	const selected_section = ref(null);
	const selected_letterhead = ref(false);
	const selected_lh_footer = ref(false);

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
	function remove_selected_fields() {
		selected_fields.value.forEach((df) => (df.remove = true));
		selected_fields.value = [];
		selected_field.value = null;
	}
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
		selected_field.value = null;
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
		selected_letterhead,
		selected_lh_footer,
		select_field,
		select_section,
		select_letterhead,
		remove_selected_fields,
		remove_field,
		align_selected_fields,
	};
}
