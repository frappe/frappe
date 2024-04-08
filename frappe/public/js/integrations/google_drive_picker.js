/* global gapi:false, google:false */
export default class GoogleDrivePicker {
	constructor({ pickerCallback, enabled, appId, clientId } = {}) {
		this.scope = "https://www.googleapis.com/auth/drive.file";
		this.pickerApiLoaded = false;
		this.enabled = enabled;
		this.appId = appId;
		this.pickerCallback = pickerCallback;
		this.clientId = clientId;
	}

	async loadPicker() {
		inject_script("https://accounts.google.com/gsi/client").then(() => {
			this.authenticate();
		});

		inject_script("https://apis.google.com/js/api.js").then(() => {
			gapi.load("client:picker", {
				callback: () => {
					gapi.client.load("https://www.googleapis.com/discovery/v1/apis/drive/v3/rest");
				},
			});
		});
	}

	authenticate() {
		const tokenClient = google.accounts.oauth2.initTokenClient({
			client_id: this.clientId,
			scope: this.scope,
			callback: async (response) => {
				if (response.error !== undefined) {
					frappe.throw(response);
				}

				this.createPicker(response.access_token);
			},
		});

		// Always try to get away with an empty prompt.
		// This will still ask for consent if the user has not given it before.
		tokenClient.requestAccessToken({ prompt: "" });
	}

	createPicker(access_token) {
		const docsView = new google.picker.DocsView();
		docsView.setParent("root"); // show the root folder by default
		docsView.setIncludeFolders(true); // also show folders, not just files

		this.picker = new google.picker.PickerBuilder()
			.setAppId(this.appId)
			.setOAuthToken(access_token)
			.addView(docsView)
			.addView(new google.picker.DocsUploadView())
			.setLocale(frappe.boot.lang)
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
		if (document.querySelector(`script[src="${src}"]`) !== null) {
			resolve();
			return;
		}

		let script = document.createElement("script");
		script.src = src;
		script.onload = resolve;
		script.onerror = reject;
		document.body.appendChild(script);
	});
}
