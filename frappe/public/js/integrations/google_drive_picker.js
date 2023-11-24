/* global gapi:false, google:false */
export default class GoogleDrivePicker {
	constructor({ pickerCallback, enabled, appId, developerKey, clientId } = {}) {
		this.scope = "https://www.googleapis.com/auth/drive.readonly";
		this.pickerApiLoaded = false;
		this.enabled = enabled;
		this.appId = appId;
		this.pickerCallback = pickerCallback;
		this.developerKey = developerKey;
		this.clientId = clientId;
		this.tokenClient = null;
		this.accessToken = null;
		this.pickerInited = false;
		this.gisInited = false;
	}

	async loadPicker() {
		await Promise.all([
			inject_script("https://apis.google.com/js/api.js"),
			inject_script("https://accounts.google.com/gsi/client"),
		]);

		// Wait for the external scripts to run
		await new Promise((resolve) => {
			const interval = setInterval(() => {
				if (typeof gapi !== "undefined" && typeof google !== "undefined") {
					clearInterval(interval);
					resolve();
				}
			}, 100);
		});

		this.libsLoaded();
	}

	libsLoaded() {
		this.tokenClient = google.accounts.oauth2.initTokenClient({
			client_id: this.clientId,
			scope: this.scope,
			callback: async (response) => {
				if (response.error !== undefined) {
					frappe.throw(response);
				}
				this.accessToken = response.access_token;
				frappe.boot.user.google_drive_token = response.access_token;
				await this.createPicker();
			},
		});
		this.gisInited = true;
		gapi.load("client:picker", { callback: this.initializePicker.bind(this) });
		if (frappe.boot.user.google_drive_token === null) {
			// Prompt the user to select a Google Account and ask for consent to share their data
			// when establishing a new session.
			this.tokenClient.requestAccessToken({ prompt: "consent" });
		} else {
			// Skip display of account chooser and consent dialog for an existing session.
			this.tokenClient.requestAccessToken({ prompt: "" });
		}
	}
	async initializePicker() {
		gapi.client.load("https://www.googleapis.com/discovery/v1/apis/drive/v3/rest");
		this.pickerInited = true;
	}
	createPicker() {
		this.view = new google.picker.View(google.picker.ViewId.DOCS);
		this.picker = new google.picker.PickerBuilder()
			.setDeveloperKey(this.developerKey)
			.setAppId(this.appId)
			.setOAuthToken(this.accessToken)
			.addView(this.view)
			.addView(new google.picker.DocsUploadView())
			.setCallback(this.pickerCallback)
			.build();
		this.picker.setVisible(true);
		this.setupHide();
	}
	setupHide() {
		let bg = document.querySelectorAll(".picker-dialog-bg");

		for (const el of bg) {
			el.addEventListener("click", () => {
				this.picker.dispose();
			});
		}
	}
}

function inject_script(src) {
	return new Promise((resolve, reject) => {
		let script = document.createElement("script");
		script.src = src;
		script.onload = resolve;
		script.onerror = reject;
		document.body.appendChild(script);
	});
}
