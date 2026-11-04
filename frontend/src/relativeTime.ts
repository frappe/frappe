// One reading of "3 days ago" for every relative date: list cells and the index's recent list.
import { currentSession } from "@framework/ui/useSession";
import { dayjs } from "frappe-ui";

type Stamp = ReturnType<typeof dayjs>;

const SKEW_MS = 60_000;
const DAY_MS = 86_400_000;

// dayjs' own breakpoints, so a language other than English switches units where English does.
const UNITS: [Intl.RelativeTimeFormatUnit, number, number][] = [
	["second", 1000, 45_000],
	["minute", 60_000, 45 * 60_000],
	["hour", 3_600_000, 22 * 3_600_000],
	["day", DAY_MS, 26 * DAY_MS],
	["month", 30 * DAY_MS, 11 * 30 * DAY_MS],
];

// Frappe's Serbian Latin; Intl would resolve `sr-CS` to Cyrillic.
const INTL_TAGS: Record<string, string> = { "sr-CS": "sr-Latn" };

const formatters = new Map<string, Intl.RelativeTimeFormat | null>();

/** `stamp` as time from now, in the signed-in person's language. A stamp under a minute ahead is clock skew and reads as just past. */
export function relativeTime(stamp: Stamp): string {
	if (!stamp.isValid()) return "";
	const lang = currentSession()?.lang || "en";
	const now = dayjs();
	const ahead = stamp.diff(now);
	const when = ahead > 0 && ahead < SKEW_MS ? now : stamp;
	const diff = when.diff(now);
	const [unit, size] = UNITS.find(([, , limit]) => Math.abs(diff) < limit) ?? ["year", 365 * DAY_MS];
	// "now" for the seconds; counted units elsewhere, as English's "a day ago" is, not "yesterday".
	const formatter = relativeFormatter(lang, unit === "second" ? "auto" : "always");
	if (!formatter) return when.fromNow();
	// Round the distance, not the signed value, so 90 seconds back and ahead read alike.
	return formatter.format(unit === "second" ? 0 : Math.sign(diff) * Math.round(Math.abs(diff) / size), unit);
}

// English keeps dayjs' wording ("a few seconds ago"); another language, or one the browser lacks, goes through Intl.
function relativeFormatter(lang: string, numeric: "auto" | "always"): Intl.RelativeTimeFormat | null {
	const key = `${lang}|${numeric}`;
	if (!formatters.has(key)) formatters.set(key, createFormatter(lang, numeric));
	return formatters.get(key) ?? null;
}

function createFormatter(lang: string, numeric: "auto" | "always"): Intl.RelativeTimeFormat | null {
	const tag = lang.replace("_", "-");
	if (tag.split("-")[0].toLowerCase() === "en") return null;
	try {
		return new Intl.RelativeTimeFormat(INTL_TAGS[tag] ?? tag, { numeric });
	} catch {
		return null;
	}
}
