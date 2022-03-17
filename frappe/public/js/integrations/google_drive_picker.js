/* global gapi:false, google:false */
export default class GoogleDrivePicker {
	constructor({
		pickerCallback,
		enabled,
		appId,
		developerKey,
		clientId
	} = {}) {
		this.scope = ['https://www.googleapis.com/auth/drive.readonly'];
		this.pickerApiLoaded = false;
		this.enabled = enabled;
		this.appId = appId;
		this.pickerCallback = pickerCallback;
		this.developerKey = developerKey;
		this.clientId = clientId;
	}

	loadPicker() {
		// load the google API library
		$.ajax({
			method: "GET",
			url: "https://apis.google.com/js/api.js",
			dataType: "script",
			cache: true
		}).done(this.loadGapi.bind(this));
	}

	loadGapi() {
		// load auth and picker libraries
		if (!frappe.boot.user.google_drive_token) {
			gapi.load('auth', this.onAuthApiLoad.bind(this));
		}

		gapi.load('picker', this.onPickerApiLoad.bind(this));
	}

	onAuthApiLoad() {
		gapi.auth.authorize({
			'client_id': this.clientId,
			'scope': this.scope,
			'immediate': false
		}, this.handleAuthResult.bind(this));
	}

	handleAuthResult(authResult) {
		let error_map = {
			"popup_closed_by_user": __("Google Authentication was closed abruptly by the user")
		};

		if (authResult && !authResult.error) {
			frappe.boot.user.google_drive_token = authResult.access_token;
			this.createPicker();
		} else {
			let error = error_map[authResult.error] || __("Google Authentication Error");
			frappe.throw(error);
		}
	}

	onPickerApiLoad() {
		this.pickerApiLoaded = true;
		this.createPicker();
	}

	createPicker() {
		// Create and render a Picker object for searching images.
		if (this.pickerApiLoaded && frappe.boot.user.google_drive_token) {
			this.view = new google.picker.DocsView(google.picker.ViewId.DOCS)
				.setParent('root') // show the root folder by default
				.setIncludeFolders(true); // also show folders, not just files

			this.picker = new google.picker.PickerBuilder()
				.setAppId(this.appId)
				.setDeveloperKey(this.developerKey)
				.setOAuthToken(frappe.boot.user.google_drive_token)
				.addView(this.view)
				.setLocale(frappe.boot.lang)
				.setCallback(this.pickerCallback)
				.build();

			this.picker.setVisible(true);
			this.setupHide();
		}
	}

	setupHide() {
		let bg = $(".picker-dialog-bg");

		for (let el of bg) {
			el.onclick = () => {
				this.picker.setVisible(false);
				this.picker.Ob({
					action: google.picker.Action.CANCEL
				});
			};
		}
	}
}
