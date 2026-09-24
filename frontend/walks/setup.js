// What the walk decides before it starts: the report path, the networks, the target doctype
// and its list path, and the login.

import { request as requestApi } from "playwright";

export const BASE_URL = process.env.BASE_URL || "http://localhost:8000";
const USR = process.env.USR || "Administrator";
const PWD_FRAPPE = process.env.PWD_FRAPPE || "admin";
const DOCTYPE = process.env.DOCTYPE;
const NETWORK = process.env.NETWORK;

const KILOBITS = 1000 / 8;

export const NETWORKS = {
	normal: { capMs: 15000, conditions: null },
	slow: {
		capMs: 120000,
		conditions: {
			offline: false,
			latency: 400,
			downloadThroughput: 400 * KILOBITS,
			uploadThroughput: 400 * KILOBITS,
		},
	},
};

export async function setUp() {
	const jsonPath = jsonPathArgument();
	const networks = networkNames();
	const target = await resolveTarget();
	return { jsonPath, networks, target };
}

function jsonPathArgument() {
	const index = process.argv.indexOf("--json");
	if (index === -1) return null;
	const path = process.argv[index + 1];
	if (!path || path.startsWith("--")) throw new Error("--json needs a path");
	return path;
}

function networkNames() {
	if (!NETWORK) return Object.keys(NETWORKS);
	if (!NETWORKS[NETWORK])
		throw new Error(`Unknown NETWORK "${NETWORK}"; use ${Object.keys(NETWORKS).join(" or ")}`);
	return [NETWORK];
}

async function resolveTarget() {
	const request = await requestApi.newContext();
	try {
		await logIn(request);
		const desk = await deskBoot(request);
		const doctype = DOCTYPE || (await firstWithRows(request, navigationDoctypes(desk)));
		return { doctype, listPath: listPathOf(desk, doctype) };
	} finally {
		await request.dispose();
	}
}

export async function logIn(request) {
	const response = await request.post(`${BASE_URL}/api/method/login`, {
		form: { usr: USR, pwd: PWD_FRAPPE },
	});
	if (!response.ok()) throw new Error(`Login failed with ${response.status()}`);
}

async function deskBoot(request) {
	const index = await getMethod(request, "frappe.shell.boot.get_boot", { path: "/apps" });
	const desk = index.apps.find((entry) => entry.app === "frappe");
	const boot = await getMethod(request, "frappe.shell.boot.get_boot", { path: desk.route });
	const addresses = await getMethod(request, "frappe.shell.doctypes.get_addresses", {
		v: boot.metadata_version,
	});
	const { modular } = boot.prefixes[desk.prefix];
	return { route: desk.route, modular, navigation: boot.navigation, addresses };
}

async function getMethod(request, method, params) {
	const response = await request.get(`${BASE_URL}/api/v2/method/${method}`, { params });
	if (!response.ok()) throw new Error(`${method} failed with ${response.status()}`);
	return (await response.json()).data;
}

function navigationDoctypes({ navigation, addresses }) {
	const items = [navigation.rail, ...Object.values(navigation.sidebars ?? {})].flat();
	return items
		.filter((item) => item.item_type === "DocType")
		.map((item) => item.link_to)
		.filter((doctype) => addresses.doctypes[doctype] && !addresses.singles?.includes(doctype));
}

async function firstWithRows(request, doctypes) {
	for (const doctype of doctypes) {
		const url = `${BASE_URL}/api/v2/document/${encodeURIComponent(doctype)}`;
		const response = await request.get(url, { params: { limit: 1 } });
		if (response.ok() && (await response.json()).data.length) return doctype;
	}
	throw new Error("No doctype in the navigation has rows; set DOCTYPE.");
}

function listPathOf(desk, doctype) {
	const address = desk.addresses.doctypes[doctype];
	if (!address) throw new Error(`DOCTYPE ${doctype} has no desk address`);
	const [slug, moduleSlug] = address;
	return [desk.route, desk.modular && moduleSlug, slug].filter(Boolean).join("/");
}
