// The v2 boot: a NEW small payload, not `frappe.sessions.get()`.
//
// #42070 measured the existing boot at 147,711 bytes, ~120 KB of it desk v1 workspace
// furniture. That is why CRM and Gameplan each rebuilt the generic keys by hand. This
// one starts small; v1's is left untouched and retires with v1.

export type Boot = {
  // --- framework core ---
  frappe_version: string;
  site_name: string;
  socketio_port: number;
  read_only_mode: boolean;
  csrf_token: string;
  setup_complete: boolean;
  sysdefaults: Record<string, unknown>;
  timezone: string;
  user: { name: string; full_name: string; user_image?: string };
  lang: string;
  translations_version: string;
  app_order: string[];

  // --- routing ---
  //
  // `shell_base` is the router's base: the COMPOSED path (`/apps/crm`), not the bare
  // segment. Boot carries it composed so the literal `/apps` never has to appear in
  // JS at all (#42125). It is `/apps` itself on the index, which belongs to no app.
  shell_base: string;
  app: string | null;

  // #42066's `{prefix: app}` registry, widened to carry #42211's modularity boolean.
  // Every active app, not just this one: a link to a foreign app's doctype needs that
  // app's shape, and one boolean per app is five entries on this bench.
  prefixes: Record<string, { app: string; modular: boolean }>;

  // The key that invalidates the ADDRESS TABLE, which is fetched separately and is
  // not in here -- it went full-bench when the prefix became a lens and broke the
  // 40 KB budget (#42210). Same treatment as `translations_version`.
  metadata_version: string;

  // Present on the index only (#42124).
  apps?: {
    app: string;
    prefix: string;
    title: string;
    logo?: string;
    route: string;
  }[];

  // --- the declaring app's contribution, merged under core (#42070) ---
  [appKey: string]: unknown;
};

export class BootUnauthorized extends Error {}

export async function fetchBoot(): Promise<Boot> {
  // `location.pathname` is the only input the client has: the document carries
  // nothing. Composition is prefix-dependent, so the server needs the path to know
  // which app's contribution to merge in.
  const res = await fetch(
    `/api/method/frappe.shell.boot.get_boot?path=${encodeURIComponent(
      location.pathname
    )}`,
    { headers: { Accept: "application/json" } }
  );

  // 401 as well as 403: an expired session answers 401, and treating it as a generic
  // failure would show "something went wrong" where the user needs a way back to login.
  if (res.status === 401 || res.status === 403)
    throw new BootUnauthorized("Not permitted");
  if (!res.ok) throw new Error(`Boot failed with ${res.status}`);

  return (await res.json()).message;
}
