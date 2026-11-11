import { ref } from "vue";

export function parseJsonFieldInput(value) {
	if (!value) return "";
	try {
		return JSON.parse(value);
	} catch {
		return String(value);
	}
}

/** Typed JSON text is only worth saving once it parses: half-typed text stays in the box. */
export function isCommittableJson(text) {
	if (!String(text ?? "").trim()) return true;
	try {
		JSON.parse(text);
		return true;
	} catch {
		return false;
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

	// Another editor (the Advanced JSON) may have changed the params under the cached rows.
	function sync() {
		const current = JSON.stringify(rowsToParams(paramsToRows(getParams())).values);
		if (JSON.stringify(rowsToParams(rows.value).values) !== current) reload();
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

	return { rows, reload, sync, setRow, addRow, removeRow };
}
