// Server calls straight to `/api/method`, so a failure comes back to the island instead of
// opening one of desk's error dialogs over the page.

export async function get(method, params = {}) {
	const query = new URLSearchParams(params).toString();
	return request(`/api/method/${method}?${query}`, { method: "GET" });
}

export async function post(method, params = {}) {
	return request(`/api/method/${method}`, {
		method: "POST",
		headers: {
			"Content-Type": "application/json",
			"X-Frappe-CSRF-Token": window.frappe?.csrf_token || window.csrf_token || "",
		},
		body: JSON.stringify(params),
	});
}

async function request(url, options) {
	const response = await fetch(url, {
		...options,
		headers: { Accept: "application/json", ...options.headers },
	});
	const body = await response.json().catch(() => ({}));
	if (!response.ok) {
		const error = new Error(server_message(body) || `${url} failed with ${response.status}`);
		error.status = response.status;
		throw error;
	}
	return body.message;
}

// the first message the server raised, as text
function server_message(body) {
	try {
		const html = JSON.parse(JSON.parse(body._server_messages)[0]).message;
		return new DOMParser().parseFromString(html, "text/html").body.textContent;
	} catch {
		return null;
	}
}
