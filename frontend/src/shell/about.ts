// What the About dialog shows: the installed apps from `get_versions`, current app first.
import { runMethod } from "@framework/ui/api";

/** One app in `frappe.utils.change_log.get_versions`. */
export interface AppVersion {
	title: string;
	description: string;
	version: string;
	branch: string;
	branch_version?: string;
	logo: string | null;
}

export type AppVersions = Record<string, AppVersion>;

export interface AboutApp extends AppVersion {
	name: string;
}

export async function loadVersions(): Promise<AppVersions> {
	const { data } = await runMethod<AppVersions>("frappe.utils.change_log.get_versions", {}, { http: "GET" });
	return data;
}

/** `1.2.3 (version-15)`; a `pr-*` branch is a checkout detail, not worth showing. */
export function versionText(app: AppVersion): string {
	const hidden = !app.branch || /^pr-\d+/i.test(app.branch);
	return hidden ? app.version : `${app.version} (${app.branch})`;
}

/** What one app's copy button copies. */
export function appLine(name: string, app: AppVersion): string {
	return `${name}: ${app.version}`;
}

/** The current app for the header; Frappe Framework when there is no product app. */
export function headerApp(versions: AppVersions, current: string | null): AboutApp | null {
	const name = current && versions[current] ? current : "frappe";
	return versions[name] ? { name, ...versions[name] } : null;
}

/** The installed apps under the header: Frappe Framework first, then the rest in install order. */
export function listedApps(versions: AppVersions, header: string | undefined): AboutApp[] {
	const names = Object.keys(versions).filter((name) => name !== header);
	names.sort((a, b) => Number(b === "frappe") - Number(a === "frappe"));
	return names.map((name) => ({ name, ...versions[name] }));
}

/** A fenced JSON block of every app's version, for a bug report. */
export function allVersionsBlock(versions: AppVersions): string {
	const flat = Object.fromEntries(
		Object.entries(versions).map(([name, app]) => [name, app.branch_version || app.version])
	);
	return "```json\n" + JSON.stringify(flat, null, "\t") + "\n```";
}
