import { ref } from "vue";

export function parseJsonFieldInput(value) {
	if (!value) return "";
	try {
		return JSON.parse(value);
	} catch {
		return String(value);
	}
}

export function formatJsonFieldValue(value) {
	return value && typeof value === "object" ? JSON.stringify(value, null, 2) : value;
}

/** Set Field Value reads `field`/`value` and `values` alike as rows, and writes only `values`. */
export function paramsToRows(params) {
	const rows = [];
	if (params.field) rows.push({ field: params.field, value: params.value ?? "" });

	const values = params.values && typeof params.values === "object" ? params.values : {};
	for (const [field, value] of Object.entries(values)) {
		rows.push({ field, value });
	}

	return rows.length ? rows : [{ field: "", value: "" }];
}

export function rowsToParams(rows) {
	const values = {};
	for (const row of rows) {
		if (row.field) values[row.field] = row.value;
	}

	return { field: null, value: null, values };
}

/** Rows keep their own list: an empty row has no params to derive it from. */
export function useFieldRows(getParams, write) {
	const rows = ref(paramsToRows(getParams()));

	function reload() {
		rows.value = paramsToRows(getParams());
	}

	function commit(next) {
		rows.value = next;
		write({ ...getParams(), ...rowsToParams(next) });
	}

	function setRow(index, key, value) {
		commit(
			rows.value.map((row, position) => {
				if (position !== index) return { ...row };
				return key === "field" ? { field: value, value: "" } : { ...row, [key]: value };
			})
		);
	}

	function addRow() {
		commit([...rows.value, { field: "", value: "" }]);
	}

	function removeRow(index) {
		commit(rows.value.filter((row, position) => position !== index));
	}

	return { rows, reload, setRow, addRow, removeRow };
}
