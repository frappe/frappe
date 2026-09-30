// A DocType change the record page does not show: a Quick Entry Form Layout the walk saves and deletes.

import { withRequest } from "./cachedScript.js";
import { BASE_URL } from "./setup.js";

const DOCUMENTS = `${BASE_URL}/api/v2/document/Form%20Layout`;
// Marks the walk's own rows, so the walk deletes nothing else.
const MARKER = "doc.name == 'return-visit-walk'";

/** Saves a marked Quick Entry layout; the server tells open desks that the DocType changed. */
export function changeDoctype(doctype) {
	return withRequest(async (request) => {
		const row = { dt: doctype, type: "Quick Entry", layout: "[]", condition: MARKER };
		const response = await request.post(DOCUMENTS, { data: row });
		if (!response.ok()) throw new Error(`Form Layout insert failed with ${response.status()}`);
	});
}

export function removeDoctypeChange() {
	return withRequest(async (request) => {
		const params = {
			filters: JSON.stringify([["condition", "=", MARKER]]),
			fields: '["name"]',
		};
		const found = await request.get(DOCUMENTS, { params });
		if (!found.ok()) throw new Error(`Form Layout read failed with ${found.status()}`);
		for (const { name } of (await found.json()).data ?? []) {
			const response = await request.delete(`${DOCUMENTS}/${name}`);
			if (!response.ok() && response.status() !== 404)
				throw new Error(`Form Layout delete failed with ${response.status()}`);
		}
	});
}
