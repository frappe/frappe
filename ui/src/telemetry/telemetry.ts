import { reactive, readonly, ref, type App } from "vue";
import type { Router, RouteLocationNormalized } from "vue-router";

import {
  fetchBootConfig,
  loadPulseClient,
  type BootConfig,
  type PulseAnonymousMode,
  type PulseClient,
  type PulseContext,
} from "./pulse";

let client: PulseClient | null = null;
let removePageviewHook: (() => void) | null = null;

const appName = ref<string>();
const isEnabled = ref(false);

export function useTelemetry() {
  return reactive({
    isEnabled: readonly(isEnabled),
    disable: () => {
      isEnabled.value = false;
      client?.stop();
    },
    capture: (event_name: string, data: Record<string, any> = {}) => {
      if (!isEnabled.value || !appName.value) return;
      client?.capture(event_name, appName.value, data);
    },
    getDistinctId: () => client?.getDistinctId?.() ?? "",
  });
}

export interface TelemetryPluginOptions {
  app_name: string;
  host?: string;
  apiKey?: string;
  site?: string;
  enabled?: boolean;
  getContext?: () => PulseContext;
  anonymousMode?: PulseAnonymousMode;
  clientUrl?: string;
  // Pass your vue-router to auto-capture a "pageview" per navigation (new sites only,
  // site_age <= 15 days, like desk).
  router?: Router;
  // Route → PII-safe string. Defaults to the matched path pattern (e.g. "/orders/:id").
  scrubRoute?: (to: RouteLocationNormalized) => string;
}

function defaultScrubRoute(to: RouteLocationNormalized): string {
  const matched = to.matched[to.matched.length - 1];
  return matched?.path || to.path || "";
}

export const telemetryPlugin = {
  async install(app: App, options: TelemetryPluginOptions) {
    appName.value = options.app_name;

    if (!appName.value) {
      console.warn(
        `Telemetry plugin installed without app_name. \n` +
          `To enable telemetry, please provide the app_name while installing the plugin: \n` +
          `app.use(telemetryPlugin, { app_name: 'your_app_name' })`,
      );
      return;
    }

    // Explicit options win; fetch the rest from the backend (skip when self-sufficient).
    const fetched: BootConfig =
      options.host != null && options.apiKey != null
        ? {}
        : await fetchBootConfig();

    const getContext =
      options.getContext ||
      (() => ({ user: fetched.user, team: fetched.team }));

    // Reinstalls (tests, HMR, SSR-per-request) reuse the module singletons, so tear
    // down the previous client's flush timer and router hook before replacing them.
    client?.stop();
    removePageviewHook?.();
    removePageviewHook = null;

    client = await loadPulseClient({
      host: options.host ?? fetched.host,
      apiKey: options.apiKey ?? fetched.key,
      site: options.site ?? fetched.site,
      enabled: options.enabled ?? fetched.enabled ?? false,
      getContext,
      anonymousMode: options.anonymousMode,
      clientUrl: options.clientUrl ?? fetched.client_url,
    });
    if (!client) return;

    isEnabled.value = await client.init();
    if (isEnabled.value) {
      removePageviewHook = setupPageviewTracking(options, fetched.site_age);
    }
  },
};

// Older backends omit site_age → track anyway (permissive, matching desk's
// `site_age && site_age > 15` skip check).
function setupPageviewTracking(
  options: TelemetryPluginOptions,
  site_age: number | undefined,
): (() => void) | null {
  if (!options.router || (site_age && site_age > 15)) return null;

  const scrub = options.scrubRoute || defaultScrubRoute;
  let lastFullPath = "";
  const capturePageview = (to: RouteLocationNormalized) => {
    // Dedupe so the initial capture and afterEach can't double-count the same route.
    if (!isEnabled.value || !appName.value || to.fullPath === lastFullPath)
      return;
    lastFullPath = to.fullPath;
    client?.capture("pageview", appName.value, { route: scrub(to) });
  };

  // afterEach missed the initial navigation if it resolved during install's awaits,
  // so capture the landing route once the router is ready.
  options.router.isReady().then(() => {
    if (options.router) capturePageview(options.router.currentRoute.value);
  });
  return options.router.afterEach((to) => capturePageview(to));
}
