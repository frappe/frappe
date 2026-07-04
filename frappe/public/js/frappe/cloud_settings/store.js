import { reactive } from "vue";
import * as api from "./api";

const POLL_INTERVAL = 2500;
const MAX_WAIT = 3 * 60 * 1000; // give up watching a task after 3 minutes

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// Poll a bench task to completion. Returns one of:
//   "success" | "failed" | "timeout" | "gone" | "error" | "cancelled".
// "timeout"/"gone" mean the task may still be running on the bench — the caller
// should tell the user rather than claim success or failure.
export async function waitForTask(taskId, isCancelled = () => false) {
	const deadline = Date.now() + MAX_WAIT;
	while (!isCancelled()) {
		let task;
		try {
			task = await api.getTask(taskId);
		} catch {
			return "error";
		}
		const status = task && task.status;
		if (!status) return "gone";
		if (status === "running") {
			if (Date.now() > deadline) return "timeout";
			await sleep(POLL_INTERVAL);
			continue;
		}
		if (status === "success" || task.exit_code === 0) return "success";
		return "failed";
	}
	return "cancelled";
}

// One reactive store shared across tabs. Each section loads lazily on first
// open; actions refresh their own section. Tabs inject this via `store`.
export function createStore() {
	const state = reactive({
		context: frappe.boot.cloud_settings || {},
		billing: null,
		billingError: "",
		marketplace: null,
		marketplaceError: "",
		domains: null,
		domainsError: "",
	});

	async function loadBilling(force = false) {
		if (state.billing && !force) return;
		// clear any previous error
		state.billingError = "";
		try {
			state.billing = await api.getBilling();
		} catch (exception) {
			state.billingError = api.getErrorMessage(exception);
		}
	}

	async function loadMarketplace(force = false) {
		if (state.marketplace && !force) return;
		state.marketplaceError = "";
		try {
			state.marketplace = await api.getMarketplaceApps();
		} catch (exception) {
			state.marketplaceError = api.getErrorMessage(exception);
		}
	}

	async function loadDomains(force = false) {
		if (state.domains && !force) return;
		state.domainsError = "";
		try {
			state.domains = await api.getDomains();
		} catch (exception) {
			state.domainsError = api.getErrorMessage(exception);
		}
	}

	return {
		state,
		api,
		loadBilling,
		loadMarketplace,
		loadDomains,
	};
}
