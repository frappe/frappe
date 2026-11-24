import { test as base, expect } from "@playwright/test";
import { Api } from "./api";
import { ADMIN_PASSWORD, TEST_USER, site_url } from "./config";
import { start_coverage, stop_coverage } from "./coverage";
import { Desk } from "./desk";

async function login(request, email, password) {
	const res = await request.post("/api/method/login", { data: { usr: email, pwd: password } });
	expect(res.status(), `login as ${email}: ${await res.text()}`).toBe(200);
}

export const test = base.extend({
	// playwright only accepts a destructuring pattern as the first argument
	// eslint-disable-next-line no-empty-pattern
	baseURL: async ({}, use, testInfo) => {
		await use(site_url(testInfo.parallelIndex));
	},

	storageState: async ({ playwright, baseURL }, use) => {
		const request = await playwright.request.newContext({ baseURL });
		await login(request, TEST_USER, ADMIN_PASSWORD);
		const state = await request.storageState();
		await request.dispose();
		await use(state);
	},

	page: async ({ page }, use, testInfo) => {
		await start_coverage(page);
		await use(page);
		await stop_coverage(page, testInfo.file);
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
				baseURL: site_url(workerInfo.parallelIndex),
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
		shared.context = await browser.newContext({
			baseURL: site_url(workerInfo.parallelIndex),
			viewport: workerInfo.project.use.viewport,
			storageState: undefined,
		});
		shared.page = await shared.context.newPage();
		await start_coverage(shared.page);
		shared.api = new Api(shared.page.request, shared.page);
		shared.desk = new Desk(shared.page, shared.api);
		await shared.desk.login(user);
	});

	// eslint-disable-next-line no-empty-pattern
	test.afterAll(async ({}, testInfo) => {
		try {
			await teardown?.(shared);
			await stop_coverage(shared.page, testInfo.file);
		} finally {
			await shared.context?.close();
		}
	});

	return shared;
}

export const GUEST = { cookies: [], origins: [] };

export { expect, ADMIN_PASSWORD, TEST_USER };
