// This file is used to make sure that `moment` is bound to the window
// before the bundle finishes loading, due to imports (datetime.js) in the bundle
// that depend on `moment`.
import momentTimezone from "moment-timezone/builds/moment-timezone-with-data-10-year-range.min.js";
window.moment = momentTimezone;
