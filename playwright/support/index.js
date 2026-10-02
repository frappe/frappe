import { test as base, expect } from "@playwright/test";
import { Api } from "./api";
import { ADMIN_PASSWORD, TEST_USER } from "./config";
import { Desk } from "./desk";

async function login(request, email, password) {
	const res = await request.post("/api/method/login", { data: { usr: email, pwd: password } });
	expect(res.status(), `login as ${email}: ${await res.text()}`).toBe(200);
}

export const test = base.extend({
	storageState: async ({ playwright, baseURL }, use) => {
		const request = await playwright.request.newContext({ baseURL });
		await login(request, TEST_USER, ADMIN_PASSWORD);
		const state = await request.storageState();
		await request.dispose();
		await use(state);
	},

	api: async ({ page }, use) => {
		await use(new Api(page.request, page));
	},

	desk: async ({ page, api }, use) => {
		await use(new Desk(page, api));
	},

	admin: [
		async ({ playwright }, use, workerInfo) => {
			const request = await playwright.request.newContext({
				baseURL: workerInfo.project.use.baseURL,
			});
			await login(request, "Administrator", ADMIN_PASSWORD);
			await use(new Api(request));
			await request.dispose();
		},
		{ scope: "worker" },
	],
});

export function use_shared_page({ user = TEST_USER, teardown } = {}) {
	const shared = {};

	test.describe.configure({ mode: "serial" });

	test.beforeAll(async ({ browser }, workerInfo) => {
		const { baseURL, viewport } = workerInfo.project.use;
		shared.context = await browser.newContext({ baseURL, viewport, storageState: undefined });
		shared.page = await shared.context.newPage();
		shared.api = new Api(shared.page.request, shared.page);
		shared.desk = new Desk(shared.page, shared.api);
		await shared.desk.login(user);
	});

	test.afterAll(async () => {
		try {
			await teardown?.(shared);
		} finally {
			await shared.context?.close();
		}
	});

	return shared;
}

export const GUEST = { cookies: [], origins: [] };

export { expect, ADMIN_PASSWORD, TEST_USER };
