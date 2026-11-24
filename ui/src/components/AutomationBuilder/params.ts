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
  return value && typeof value === "object"
    ? JSON.stringify(value, null, 2)
    : value;
}

/**
 * Set Field Value stores either a single `field`/`value` pair or a `values` map, and the
 * engine applies both. The editor works in rows, so both shapes read in as rows and every
 * row writes back into `values` - one shape to reason about, whatever the flow was saved as.
 */
export function paramsToRows(params) {
  const rows = [];
  if (params.field)
    rows.push({ field: params.field, value: params.value ?? "" });

  const values =
    params.values && typeof params.values === "object" ? params.values : {};
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

/**
 * Row editing owns its own list rather than deriving it from the stored params: an empty row
 * has nothing to store, so a list derived from params could never show one and "Add field"
 * would appear to do nothing. Params stay the source of truth for everything already filled.
 */
export function useFieldRows(getParams, write) {
  const rows = ref(paramsToRows(getParams()));
  let mirrored = JSON.stringify(getParams());

  function reload() {
    rows.value = paramsToRows(getParams());
    mirrored = JSON.stringify(getParams());
  }

  function sync() {
    const incoming = JSON.stringify(getParams());
    if (incoming === mirrored) return;
    const unfinished = rows.value.filter((row) => !row.field);
    const saved = paramsToRows(getParams()).filter((row) => row.field);
    rows.value = [...saved, ...unfinished];
    if (!rows.value.length) rows.value = [{ field: "", value: "" }];
    mirrored = incoming;
  }

  function commit(next) {
    rows.value = next;
    const params = { ...getParams(), ...rowsToParams(next) };
    mirrored = JSON.stringify(params);
    write(params);
  }

  function setRow(index, key, value) {
    commit(
      rows.value.map((row, position) => {
        if (position !== index) return { ...row };
        return key === "field"
          ? { field: value, value: "" }
          : { ...row, [key]: value };
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
