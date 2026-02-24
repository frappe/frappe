/**
 * Frappe Playwright test utilities.
 * Mirrors the most-used custom Cypress commands in cypress/support/commands.js.
 */

/**
 * Log into Frappe via the REST API and return the authenticated context.
 * Call this in a beforeAll / beforeEach to get an already-logged-in page.
 */
async function login(page, email, password) {
	email = email || process.env.ADMIN_USER || "Administrator";
	password = password || process.env.ADMIN_PASSWORD || "admin";

	await page.request.post("/api/method/login", {
		data: { usr: email, pwd: password },
	});
}

/**
 * Log out the current user by calling the logout whitelisted method.
 * Uses the CSRF token from the current page context.
 */
async function logout(page) {
	const csrfToken = await page.evaluate(() => window.frappe?.csrf_token);
	if (csrfToken) {
		await page.request.post("/api/method/logout", {
			headers: {
				"X-Frappe-CSRF-Token": csrfToken,
			},
		});
	} else {
		// Fallback: just hit logout without CSRF (works for GET logout too)
		await page.request.post("/api/method/logout");
	}
}

/**
 * Call a Frappe whitelisted method. Retrieves the CSRF token from the page.
 */
async function frappeCall(page, method, args) {
	const csrfToken = await page.evaluate(() => window.frappe?.csrf_token);
	const headers = {
		Accept: "application/json",
		"Content-Type": "application/json",
	};
	if (csrfToken) {
		headers["X-Frappe-CSRF-Token"] = csrfToken;
	}
	const response = await page.request.post(`/api/method/${method}`, {
		data: args || {},
		headers,
	});
	return response.json();
}

module.exports = { login, logout, frappeCall };
