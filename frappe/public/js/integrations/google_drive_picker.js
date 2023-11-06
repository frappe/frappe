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

	loadPicker() {
		$.when(ajax_gapi(), ajax_gis()).done(this.libsLoaded.bind(this));
		// load the google identity service library
		function ajax_gis() {
			return $.ajax({
				method: "GET",
				url: "https://accounts.google.com/gsi/client",
				dataType: "script",
				cache: true,
			});
		}

		function ajax_gapi() {
			// load the google API library
			$.ajax({
				method: "GET",
				url: "https://apis.google.com/js/api.js",
				dataType: "script",
				cache: true,
			});
		}
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
			.enableFeature(google.picker.Feature.MULTISELECT_ENABLED)
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
		let bg = $(".picker-dialog-bg");

		for (let el of bg) {
			el.onclick = () => {
				this.picker.setVisible(false);
				this.picker.Ob({
					action: google.picker.Action.CANCEL,
				});
			};
		}
	}
}
