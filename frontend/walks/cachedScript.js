// The stored Client Script the walk gives its doctype: a header item drawn from `page.cached`.

import { request as requestApi } from "playwright";
import { BASE_URL, logIn } from "./setup.js";

export const PENDING = "page.cached pending";

const NAME = "Return Visit Walk";
const DOCUMENTS = `${BASE_URL}/api/v2/document/Client%20Script`;

const SOURCE = `import { h } from "vue";

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
		const label = count === undefined ? ${JSON.stringify(PENDING)} : "Rows: " + count;
		page.header.add({ name: "walk-cached", label, component: Count, props: { label } });
	},
};
`;

export function installCachedScript(doctype) {
	return withRequest(async (request) => {
		await remove(request);
		const script = { name: NAME, dt: doctype, view: "Record", enabled: 1, script: SOURCE };
		const response = await request.post(DOCUMENTS, { data: script });
		if (!response.ok()) throw new Error(`Client Script insert failed with ${response.status()}`);
	});
}

export function removeCachedScript() {
	return withRequest(remove);
}

async function withRequest(work) {
	const request = await requestApi.newContext();
	try {
		await logIn(request);
		return await work(request);
	} finally {
		await request.dispose();
	}
}

async function remove(request) {
	const response = await request.delete(`${DOCUMENTS}/${encodeURIComponent(NAME)}/`);
	if (!response.ok() && response.status() !== 404)
		throw new Error(`Client Script delete failed with ${response.status()}`);
}
