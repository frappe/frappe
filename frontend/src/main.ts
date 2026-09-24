// The mount sequence. Boot resolves first: the router's base and shape come out of it.

import "@/index.css";
import { createApp, h } from "vue";
import { FrappeUI } from "frappe-ui";
import { provideSession } from "@framework/ui/composables/useSession";
// the types module, not the subsystem barrel: the shell must not load the dialog to boot
import { UploadLimitsKey } from "@framework/ui/components/FileUpload/types";

import { fetchBoot, BootUnauthorized, type Boot } from "@/boot";
import { fetchAddresses, type Addresses } from "@/addresses";
import { createShellRouter } from "@/router";
import { registerShell } from "@/router/routeFor";
import { loadTranslations } from "@/i18n";
import { loadSprite, symbolGeometry } from "@/icons/sprite";
import { setDrawnProps, setIconSource, watchClientScripts } from "@/recordPage";
import { recordDrawnProps } from "@/pages/record/drawnProps";
import { registerContributions } from "@/contributions/registry";
import AppShell from "@/shell/AppShell.vue";
import { createSocket } from "@/shell/socket";
import { watchDoctypeUpdates } from "@/shell/doctypeUpdates";
import Unauthorized from "@/shell/Unauthorized.vue";
import BootError from "@/shell/BootError.vue";

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
	loadTranslations(boot.translations_version, boot.session.lang);
	loadSprite();
	setIconSource(symbolGeometry);
	setDrawnProps(recordDrawnProps());

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
	app.use(FrappeUI);
	// Where `getSocketInstance` looks; the plugin no longer opens one.
	app.config.globalProperties.$socket = createSocket(boot);
	watchClientScripts(app.config.globalProperties.$socket);
	watchDoctypeUpdates(app.config.globalProperties.$socket);
	app.use(router);
	app.provide("boot", boot);
	provideSession(app, boot.session);
	// The site's own upload limits; the upload primitive reads them by injection.
	app.provide(UploadLimitsKey, {
		max_file_size: boot.max_file_size,
		file_chunk_size: boot.file_chunk_size,
	});
	app.provide("addresses", addresses);
	app.mount("#app");
}

start();
