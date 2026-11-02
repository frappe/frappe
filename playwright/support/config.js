export const TEST_USER = process.env.TEST_USER || "frappe@example.com";
export const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD || "admin";

const base_urls = [
	process.env.BASE_URL || "http://localhost:8000",
	...(process.env.PARALLEL_BASE_URLS || "").split(",").filter(Boolean),
];

export const WORKERS = base_urls.length;
export const site_url = (parallel_index) => base_urls[parallel_index];
