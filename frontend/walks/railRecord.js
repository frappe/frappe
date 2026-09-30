// The Record item the view-restore walk adds to the login user's desk rail, and deletes.

import { withRequest } from "./cachedScript.js";
import { BASE_URL, USR } from "./setup.js";

export const RAIL_KEY = "view-restore-walk";

const RAILS = `${BASE_URL}/api/v2/document/Rail`;
const RECORD_KIND = `${BASE_URL}/api/v2/document/Navigation%20Item%20Type/Record`;
const LAYER = { app: "frappe", extends: "", user: USR, standard: 0 };

let createdLayer = null;

/** Adds the item to the user's rail layer; false when the site has no `Record` item kind. */
export function storeRailRecord(doctype, name) {
	return withRequest(async (request) => {
		await remove(request);
		const kind = await request.get(RECORD_KIND);
		if (kind.status() === 404) return false;
		if (!kind.ok()) throw new Error(`Navigation Item Type read failed with ${kind.status()}`);
		const item = { key: RAIL_KEY, added: 1, item_type: "Record", link_doctype: doctype };
		const layer = await userLayer(request);
		const items = [...(layer?.items ?? []), { ...item, link_to: name }];
		const response = layer
			? await request.patch(`${RAILS}/${layer.name}`, { data: { items } })
			: await request.post(RAILS, { data: { ...LAYER, items } });
		if (!response.ok()) throw new Error(`Rail save failed with ${response.status()}`);
		if (!layer) createdLayer = (await response.json()).data.name;
		return true;
	});
}

export function removeRailRecord() {
	return withRequest(remove);
}

/** Deletes only rows keyed `RAIL_KEY`, and the layer when this run made it and nothing else is left. */
async function remove(request) {
	const layer = await userLayer(request);
	const items = layer?.items.filter((item) => item.key !== RAIL_KEY);
	if (!layer || items.length === layer.items.length) return;
	const url = `${RAILS}/${layer.name}`;
	const response =
		items.length || layer.name !== createdLayer
			? await request.patch(url, { data: { items } })
			: await request.delete(url);
	if (!response.ok()) throw new Error(`Rail cleanup failed with ${response.status()}`);
}

async function userLayer(request) {
	const filters = Object.entries(LAYER).map(([field, value]) => [field, "=", value]);
	const params = { filters: JSON.stringify(filters), fields: '["name"]' };
	const found = await request.get(RAILS, { params });
	if (!found.ok()) throw new Error(`Rail read failed with ${found.status()}`);
	const [row] = (await found.json()).data ?? [];
	if (!row) return null;
	const response = await request.get(`${RAILS}/${row.name}`);
	if (!response.ok()) throw new Error(`Rail read failed with ${response.status()}`);
	return (await response.json()).data;
}
