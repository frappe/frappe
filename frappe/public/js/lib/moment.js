// This file is used to make sure that `moment` is bound to the window
// before the bundle finishes loading, due to imports (datetime.js) in the bundle
// that depend on `moment`.
import momentTimezone from "moment-timezone/builds/moment-timezone-with-data-10-year-range.min.js";
// The timezone build ships no locale data, so moment.locale() silently keeps
// English. Without these, relative dates ("3 days ago") stay English in every
// language.
import "moment/min/locales";
window.moment = momentTimezone;
