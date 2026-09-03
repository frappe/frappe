// The mount sequence. Boot resolves first: the router's base and shape come out of it.

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
	// Nothing renders before boot: the user, the timezone and the CSRF token are in it.
	let boot: Boot;
	try {
		boot = await fetchBoot();
	} catch (error) {
		// The shell owns every error state; an app cannot brand it.
		const fallback =
			error instanceof BootUnauthorized ? Unauthorized : BootError;
		createApp(h(fallback, { error: String(error) })).mount("#app");
		return;
	}

	// Translations and the icon sprite are fired, not awaited.
	loadTranslations(boot.translations_version, boot.lang);
	loadSprite();

	// The address table is awaited: the route table cannot resolve a URL without it, and
	// it is keyed on `boot.metadata_version`, so it cannot be fetched alongside boot.
	let addresses: Addresses;
	try {
		addresses = await fetchAddresses(boot.metadata_version);
	} catch (error) {
		createApp(h(BootError, { error: String(error) })).mount("#app");
		return;
	}

	// Contributions register before the router's first resolution.
	await registerContributions(boot.app_order);

	// Only now is the base known, and the shape: a modular app's route table is one segment deeper.
	const router = createShellRouter(boot, addresses);

	// Fill the shell slot before anything can call `routeFor`.
	registerShell({ boot, addresses, router });

	const app = createApp(AppShell);
	app.use(FrappeUI, { socketio: { port: boot.socketio_port } });
	app.use(router);
	app.provide("boot", boot);
	app.provide("addresses", addresses);
	app.mount("#app");
}

start();
