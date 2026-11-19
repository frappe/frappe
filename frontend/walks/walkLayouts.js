// The Form Layout rows one walk inserts and deletes: the rows this run inserted, or a crashed
// run's rows on the same doctype and type that carry the walk's marker condition.

import { BASE_URL } from "./setup.js";

const DOCUMENTS = `${BASE_URL}/api/v2/document/Form%20Layout`;

export class WalkLayouts {
	constructor(marker) {
		Object.assign(this, { marker, inserted: [] });
	}

	/** Inserts a row carrying the walk's marker condition and keeps its name. */
	async insert(request, row) {
		const data = { ...row, condition: this.marker };
		const response = await request.post(DOCUMENTS, { data });
		if (!response.ok())
			throw new Error(`${row.type} Form Layout insert failed with ${response.status()}`);
		this.inserted.push((await response.json()).data.name);
	}

	/** Deletes a crashed run's rows: on `dt`, of one of `types`, with the walk's marker condition. */
	async removeLeftovers(request, dt, types) {
		const filters = [
			["dt", "=", dt],
			["type", "in", types],
			["condition", "=", this.marker],
		];
		const params = { filters: JSON.stringify(filters), fields: '["name"]' };
		const found = await request.get(DOCUMENTS, { params });
		if (!found.ok()) throw new Error(`Form Layout read failed with ${found.status()}`);
		for (const { name } of (await found.json()).data ?? []) await remove(request, name);
	}

	/** Deletes exactly the rows this run inserted. */
	async removeInserted(request) {
		while (this.inserted.length) {
			await remove(request, this.inserted.at(-1));
			this.inserted.pop();
		}
	}
}

async function remove(request, name) {
	const response = await request.delete(`${DOCUMENTS}/${name}`);
	if (!response.ok() && response.status() !== 404)
		throw new Error(`Form Layout delete failed with ${response.status()}`);
}
