// One reading of "3 days ago" for every relative date: list cells and the index's recent list.
import { currentSession } from "@framework/ui/useSession";
import { dayjs } from "frappe-ui";
import type { Dayjs } from "dayjs";

const SKEW_MS = 60_000;

// dayjs' own breakpoints, so a language other than English switches units where English does.
const UNITS: [Intl.RelativeTimeFormatUnit, number, number][] = [
	["second", 1000, 45_000],
	["minute", 60_000, 45 * 60_000],
	["hour", 3_600_000, 22 * 3_600_000],
	["day", 86_400_000, 26 * 86_400_000],
	["month", 30 * 86_400_000, 11 * 30 * 86_400_000],
];

/** `stamp` as time from now, in the signed-in person's language. A stamp under a minute ahead is clock skew and reads as just past. */
export function relativeTime(stamp: Dayjs): string {
	const lang = currentSession()?.lang || "en";
	const now = dayjs();
	const ahead = stamp.diff(now);
	const when = ahead > 0 && ahead < SKEW_MS ? now : stamp;
	const diff = when.diff(now);
	const [unit, size] = UNITS.find(([, , limit]) => Math.abs(diff) < limit) ?? ["year", 365 * 86_400_000];
	// "now" for the seconds; counted units elsewhere, as English's "a day ago" is, not "yesterday".
	const formatter = relativeFormatter(lang, unit === "second" ? "auto" : "always");
	if (!formatter) return when.fromNow();
	return formatter.format(unit === "second" ? 0 : Math.round(diff / size), unit);
}

// English keeps dayjs' wording ("a few seconds ago"); another language, or one the browser lacks, goes through Intl.
function relativeFormatter(lang: string, numeric: "auto" | "always"): Intl.RelativeTimeFormat | null {
	if (lang.split(/[-_]/)[0].toLowerCase() === "en") return null;
	try {
		return new Intl.RelativeTimeFormat(lang.replace("_", "-"), { numeric });
	} catch {
		return null;
	}
}
