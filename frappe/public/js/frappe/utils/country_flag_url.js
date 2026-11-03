// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// Same-origin country flag SVGs for Phone fields (frappe/public/images/flags/).

export const COUNTRY_FLAG_ASSET_BASE = "/assets/frappe/images/flags";

export function get_country_flag_url(country_code) {
	const code = String(country_code || "xx").toLowerCase();
	return `${COUNTRY_FLAG_ASSET_BASE}/${encodeURIComponent(code)}.svg`;
}
