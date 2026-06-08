import countriesJson from "../../../../frappe/geo/country_info.json";
import type { Country } from "./types";

export interface PhoneDetails {
  /** Matched country, or `null` when the value carries no recognizable ISD. */
  country: Country | null;

  /** National number part of the value. */
  number: string;
}

// Sourced from the framework's canonical country dataset
// (`frappe/geo/country_info.json`); the extra currency/format fields it
// carries are unused here.
const countryData = countriesJson as Record<
  string,
  { code: string; isd?: string; timezones?: string[] }
>;

// Built once per app. Entries without a dial code (uninhabited
// territories) can't be picked in a phone control.
export const countries: readonly Country[] = Object.entries(countryData)
  .filter(([, info]) => info.isd)
  .map(([name, info]) => ({ name, code: info.code, isd: info.isd as string }))
  .sort((a, b) => a.name.localeCompare(b.name));

/**
 * Country of the browser's system timezone via `country_info.json` — a
 * location guess with no permission prompt or network call. `null` when
 * the zone is unknown; zones shared by several countries resolve to the
 * first country alphabetically.
 */
export function guessCountryFromTimezone(): Country | null {
  const timezone = getBrowserTimezone();
  return (
    countries.find((c) => countryData[c.name].timezones?.includes(timezone)) ??
    null
  );
}

/**
 * `"+ISD-NUMBER"` (canonical, split on the first hyphen),
 * `"+ISDNUMBER"` (longest-ISD-prefix match, so `"+1242…"` is the
 * Bahamas, not `+1`), else a national number with no country.
 */
export function splitPhoneDetails(value: string): PhoneDetails {
  // 1. "+91-9876…" — text before the first hyphen is an exact ISD.
  const [beforeHyphen, ...afterHyphen] = value.split("-");
  if (afterHyphen.length) {
    const country = countries.find((c) => c.isd === beforeHyphen);
    if (country) return { country, number: afterHyphen.join("-") };
  }

  // 2. "+919876…" — no hyphen: the longest matching ISD wins, so
  //    "+1242…" is the Bahamas, not the US (+1).
  const country = countries
    .filter((c) => value.startsWith(c.isd))
    .sort((a, b) => b.isd.length - a.isd.length)
    .at(0);
  if (country) return { country, number: value.slice(country.isd.length) };

  // 3. "9876…" — a national number with no recognizable ISD.
  return { country: null, number: value };
}

/** Joins into the canonical `"<isd>-<number>"`; `''` when the number is empty. */
export function joinPhoneDetails(
  country: Country | null,
  number: string
): string {
  if (!number) return "";
  return country ? `${country.isd}-${number}` : number;
}

export function getCountryFromCode(code?: string | null): Country | null {
  if (!code) return null;
  return countries.find((c) => c.code === code.toLowerCase()) ?? null;
}

/**
 * Looks a country up by any developer-friendly identifier: ISO2 code
 * (`"in"`), ISD with or without the plus (`"+91"`, `"91"`), or country
 * name (`"India"`). Case-insensitive; the three formats can't collide.
 */
export function getCountry(identifier?: string | null): Country | null {
  if (!identifier) return null;
  const query = identifier.trim().toLowerCase();

  const matches = (country: Country) =>
    country.code === query || // "in"
    country.isd === query || // "+91"
    country.isd === `+${query}` || // "91"
    country.name.toLowerCase() === query; // "india"

  return countries.find(matches) ?? null;
}

export function getFlagUrl(country: Country): string {
  return `https://flagcdn.com/${country.code}.svg`;
}

function getBrowserTimezone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone;
}
