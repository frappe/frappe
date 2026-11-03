export const COUNTRY_FLAG_ASSET_BASE = "/assets/frappe/images/flags";

export function get_country_flag_url(country_code) {
	const code = String(country_code || "xx").toLowerCase();
	return `${COUNTRY_FLAG_ASSET_BASE}/${encodeURIComponent(code)}.svg`;
}
