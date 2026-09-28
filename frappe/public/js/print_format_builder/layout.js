export function* zones(layout) {
	for (const zone of [layout?.header, ...(layout?.sections || []), layout?.footer]) {
		if (zone && typeof zone === "object") yield zone;
	}
}

export function* columns(zone) {
	for (const col of zone?.columns || []) if (col && typeof col === "object") yield col;
}

export function* fields(zone) {
	for (const col of columns(zone)) {
		for (const df of col.fields || []) if (df && !df.remove) yield df;
	}
}

export function* layout_nodes(layout) {
	for (const zone of zones(layout)) {
		yield zone;
		yield* fields(zone);
	}
}

export function zone_of(layout, section) {
	if (section && section === layout?.header) return "header";
	if (section && section === layout?.footer) return "footer";
	return null;
}

export function column_of(layout, df) {
	for (const zone of zones(layout)) {
		for (const col of columns(zone)) if (col.fields?.includes(df)) return col;
	}
	return null;
}

export function section_of(layout, df) {
	for (const zone of zones(layout)) {
		for (const col of columns(zone)) if (col.fields?.includes(df)) return zone;
	}
	return null;
}
