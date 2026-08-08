// Product telemetry for Frappe SPAs. Moved here from `frappe-ui/frappe` — the
// plugin reads its config from a Frappe backend method, so it belongs above
// frappe-ui rather than inside it.
//
// `telemetryPlugin` was frappe-ui's *default* export from `telemetry/index.ts`,
// but consumers only ever saw the re-exported name, so it is a plain named
// export here.
export { telemetryPlugin, useTelemetry } from "./telemetry";
export type { TelemetryPluginOptions } from "./telemetry";
// Referenced by `TelemetryPluginOptions.getContext` / `.anonymousMode`, so a
// consumer cannot write those options without them.
export type { PulseAnonymousMode, PulseContext } from "./pulse";
