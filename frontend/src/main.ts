// The mount sequence. Read top to bottom: it is the whole lifecycle.
//
// The ordering constraint that shapes everything: boot must land BEFORE the router is
// created, because the router's base comes out of boot. That is stronger than "the
// shell blocks on boot" -- it means the router cannot be a module-scope singleton the
// way CRM's is today (#42072).

import '@/index.css'
import { createApp, h } from 'vue'
import { FrappeUI, frappeRequest, setConfig } from 'frappe-ui'

import { fetchBoot, BootUnauthorized, type Boot } from '@/boot'
import { createShellRouter } from '@/router'
import { loadTranslations } from '@/i18n'
import { registerContributions } from '@/contributions/registry'
import AppShell from '@/shell/AppShell.vue'
import Unauthorized from '@/shell/Unauthorized.vue'
import BootError from '@/shell/BootError.vue'

setConfig('resourceFetcher', frappeRequest)

async function start() {
  // 1. BLOCK on boot. Nothing renders first -- not a spinner, not chrome. Nothing
  //    useful exists before the user, the timezone and the CSRF token do. An
  //    unauthorized user gets the shell HTML at 200 and is refused HERE (#42112).
  let boot: Boot
  try {
    boot = await fetchBoot()
  } catch (error) {
    // The shell owns every error state, including this one. An app cannot brand it.
    const fallback = error instanceof BootUnauthorized ? Unauthorized : BootError
    createApp(h(fallback, { error: String(error) })).mount('#app')
    return
  }

  // 2. Translations are fired, NOT awaited (#42070).
  loadTranslations(boot.translations_version, boot.lang)

  // 3. Contributions register before the router's first resolution -- the same
  //    invariant CRM's main.ts holds today, but the framework now owns it for every
  //    app. No per-app register.ts, and no `extend_frontend` list to walk: everything
  //    is already in this bundle (#42068, #42071).
  await registerContributions(boot.app_order)

  // 4. NOW the router, because only now is the base known.
  const router = createShellRouter(boot)

  const app = createApp(AppShell)
  app.use(FrappeUI, { socketio: { port: boot.socketio_port } })
  app.use(router)
  app.provide('boot', boot)
  app.mount('#app')
}

start()
