// The stored Client Script the walk gives its doctype: a header item drawn from `page.cached`.

import { request as requestApi } from "playwright";
import { BASE_URL, logIn } from "./setup.js";

export const PENDING = "page.cached pending";

const NAME = "Return Visit Walk";
const DOCUMENTS = `${BASE_URL}/api/v2/document/Client%20Script`;
const SCRIPT_URL = `${DOCUMENTS}/${encodeURIComponent(NAME)}/`;
const MARKER = "// Stored by the return-visit walk, which deletes it.";

// The item's label ends with the version, so a step can tell which script drew it.
function source(version) {
	return `${MARKER}
import { h } from "vue";

const Count = {
	props: ["label", "page"],
	render() {
		return h("span", { "data-walk-script": "cached" }, this.label);
	},
};

export default {
	onRefresh(page) {
		const count = page.cached("walk-count", () =>
			page.call("frappe.client.get_count", { doctype: page.doctype })
		);
		const label = count === undefined ? ${JSON.stringify(PENDING)} : "Rows: " + count + " ${version}";
		page.header.add({ name: "walk-cached", label, component: Count, props: { label } });
	},
};
`;
}

export function installCachedScript(doctype, version) {
	return withRequest(async (request) => {
		await remove(request);
		const script = {
			name: NAME,
			dt: doctype,
			view: "Record",
			enabled: 1,
			script: source(version),
		};
		const response = await request.post(DOCUMENTS, { data: script });
		if (!response.ok())
			throw new Error(`Client Script insert failed with ${response.status()}`);
	});
}

/** Saves a new version of the walk's script; the server tells open desks that it changed. */
export function changeCachedScript(version) {
	return withRequest(async (request) => {
		const response = await request.patch(SCRIPT_URL, { data: { script: source(version) } });
		if (!response.ok())
			throw new Error(`Client Script update failed with ${response.status()}`);
	});
}

export function removeCachedScript() {
	return withRequest(remove);
}

export async function withRequest(work) {
	const request = await requestApi.newContext();
	try {
		await logIn(request);
		return await work(request);
	} finally {
		await request.dispose();
	}
}

/** Deletes only the walk's own script; a script of that name without the marker stops the walk. */
async function remove(request) {
	const found = await request.get(SCRIPT_URL);
	if (found.status() === 404) return;
	if (!found.ok()) throw new Error(`Client Script read failed with ${found.status()}`);
	const { data } = await found.json();
	if (!String(data.script ?? "").startsWith(MARKER))
		throw new Error(`A Client Script named "${NAME}" exists and the walk did not make it.`);
	const response = await request.delete(SCRIPT_URL);
	if (!response.ok() && response.status() !== 404)
		throw new Error(`Client Script delete failed with ${response.status()}`);
}
