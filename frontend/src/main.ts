// The mount sequence. Read top to bottom: it is the whole lifecycle.
//
// The ordering constraint that shapes everything: boot must land BEFORE the router is
// created, because the router's base comes out of boot. That is stronger than "the
// shell blocks on boot" -- it means the router cannot be a module-scope singleton the
// way CRM's is today (#42072).

import "@/index.css";
import { createApp, h } from "vue";
import { FrappeUI, frappeRequest, setConfig } from "frappe-ui";

import { fetchBoot, BootUnauthorized, type Boot } from "@/boot";
import { fetchAddresses, type Addresses } from "@/addresses";
import { createShellRouter } from "@/router";
import { registerShell } from "@/router/routeFor";
import { loadTranslations } from "@/i18n";
import { loadSprite } from "@/icons/sprite";
import { registerContributions } from "@/contributions/registry";
import AppShell from "@/shell/AppShell.vue";
import Unauthorized from "@/shell/Unauthorized.vue";
import BootError from "@/shell/BootError.vue";

setConfig("resourceFetcher", frappeRequest);

async function start() {
	// 1. BLOCK on boot. Nothing renders first -- not a spinner, not chrome. Nothing
	//    useful exists before the user, the timezone and the CSRF token do. An
	//    unauthorized user gets the shell HTML at 200 and is refused HERE (#42112).
	let boot: Boot;
	try {
		boot = await fetchBoot();
	} catch (error) {
		// The shell owns every error state, including this one. An app cannot brand it.
		const fallback =
			error instanceof BootUnauthorized ? Unauthorized : BootError;
		createApp(h(fallback, { error: String(error) })).mount("#app");
		return;
	}

	// 2. Translations are fired, NOT awaited (#42070).
	loadTranslations(boot.translations_version, boot.lang);

	// 2a. The icon sprite, fired and not awaited for the same reason.
	loadSprite();

	// 2b. The address table, which IS awaited -- unlike translations, because the route
	//     table cannot resolve a single URL without it and an untranslated first frame
	//     is survivable where a mis-resolved one is not. It costs a second sequential
	//     round trip on a cold load, and only a cold one: the endpoint is cached for a
	//     year and `boot.metadata_version` is the only thing that busts it. It cannot
	//     be fired in parallel with boot, since boot is where that version comes from,
	//     and the document is not allowed to carry it (#42072).
	let addresses: Addresses;
	try {
		addresses = await fetchAddresses(boot.metadata_version);
	} catch (error) {
		createApp(h(BootError, { error: String(error) })).mount("#app");
		return;
	}

	// 3. Contributions register before the router's first resolution -- the same
	//    invariant CRM's main.ts holds today, but the framework now owns it for every
	//    app. No per-app register.ts, and no `extend_frontend` list to walk: everything
	//    is already in this bundle (#42068, #42071).
	await registerContributions(boot.app_order);

	// 4. NOW the router, because only now is the base known -- and the SHAPE too: a
	//    modular app's route table is one segment deeper, and `boot.prefixes` is what
	//    says which (#42211).
	const router = createShellRouter(boot, addresses);

	// 5. Fill the shell slot before anything can call `routeFor`. Not a module-scope
	//    router (#42072 forbids one) -- a slot holding the single shell this document
	//    owns, which is what lets a contributed script build an address without being
	//    handed the router.
	registerShell({ boot, addresses, router });

	const app = createApp(AppShell);
	app.use(FrappeUI, { socketio: { port: boot.socketio_port } });
	app.use(router);
	app.provide("boot", boot);
	app.provide("addresses", addresses);
	app.mount("#app");
}

start();
