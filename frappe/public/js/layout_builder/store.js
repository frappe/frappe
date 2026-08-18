import { defineStore } from "pinia";
import { ref, computed } from "vue";

export const OVERRIDE_PROPS = [
	{
		fieldname: "label",
		label: "Label",
		fieldtype: "Data",
		description: "Override the field label for this layout",
	},
	{
		fieldname: "hidden",
		label: "Hidden",
		fieldtype: "Check",
		description: "Hide this field in the layout",
	},
	{
		fieldname: "reqd",
		label: "Required",
		fieldtype: "Check",
		description: "Make this field mandatory in the layout",
	},
	{
		fieldname: "read_only",
		label: "Read Only",
		fieldtype: "Check",
		description: "Make this field read-only in the layout",
	},
	{ fieldname: "allow_in_quick_entry", label: "Allow in Quick Entry", fieldtype: "Check" },
	{ fieldname: "bold", label: "Bold", fieldtype: "Check" },
	{ fieldname: "in_list_view", label: "In List View", fieldtype: "Check" },
	{ fieldname: "in_standard_filter", label: "In Standard Filter", fieldtype: "Check" },
	{
		fieldname: "default",
		label: "Default Value",
		fieldtype: "Data",
		description: "Override the default value",
	},
	{
		fieldname: "description",
		label: "Description",
		fieldtype: "Small Text",
		description: "Override the field description",
	},
	{
		fieldname: "depends_on",
		label: "Depends On",
		fieldtype: "Data",
		description: "eval: doc.field == 'x'",
	},
	{ fieldname: "mandatory_depends_on", label: "Mandatory Depends On", fieldtype: "Data" },
	{ fieldname: "read_only_depends_on", label: "Read Only Depends On", fieldtype: "Data" },
];

export const STRUCTURAL_TYPES = new Set(["Section Break", "Column Break", "Tab Break"]);

export const useLayoutBuilderStore = defineStore("layout-builder-store", () => {
	let frm = ref(null);
	let doc = ref(null);
	let fields = ref([]);
	let selected_field = ref(null);
	let dirty = ref(false);

	let base_meta = computed(() => {
		if (!doc.value?.document_type) return {};
		return frappe.meta.docfield_map[doc.value.document_type] || {};
	});

	function init(_frm) {
		frm.value = _frm;
		doc.value = _frm.doc;
		reload();
	}

	function reload() {
		fields.value = (frm.value.doc.fields || []).slice().sort((a, b) => a.idx - b.idx);
		selected_field.value = null;
		dirty.value = false;
	}

	function select(field_row) {
		selected_field.value = field_row;
	}

	function deselect() {
		selected_field.value = null;
	}

	function update_field(fieldname, prop, value) {
		const row = (frm.value.doc.fields || []).find((f) => f.fieldname === fieldname);
		if (!row) return;
		row[prop] = value;
		const reactive_row = fields.value.find((f) => f.fieldname === fieldname);
		if (reactive_row) reactive_row[prop] = value;
		mark_dirty();
	}

	function reorder(new_order_fieldnames) {
		const by_name = {};
		(frm.value.doc.fields || []).forEach((f) => {
			by_name[f.fieldname] = f;
		});
		frm.value.doc.fields = new_order_fieldnames
			.map((fn, i) => {
				const f = by_name[fn];
				if (f) f.idx = i + 1;
				return f;
			})
			.filter(Boolean);
		fields.value = frm.value.doc.fields.slice();
		mark_dirty();
	}

	function mark_dirty() {
		dirty.value = true;
		frm.value.dirty();
	}

	return {
		frm,
		doc,
		fields,
		selected_field,
		dirty,
		base_meta,
		init,
		reload,
		select,
		deselect,
		update_field,
		reorder,
		mark_dirty,
	};
});
