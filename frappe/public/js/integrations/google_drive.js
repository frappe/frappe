export default class GoogleDrive {
    constructor({
        pickerCallback,
        developerKey,
        clientId,
        appId
    } = {}) {
        this.pickerCallback = pickerCallback;
        this.pickerApiLoaded = false;
        this.scope = ['https://www.googleapis.com/auth/drive.readonly'];
        this.developerKey = developerKey;
        this.clientId = clientId;
        this.appId = appId;
    }

    loadPicker() {
        // load the google API library
        $.ajax({
            method: "GET",
            url: "https://apis.google.com/js/api.js",
            dataType: "script",
            cache: true,
            context: this
        }).done(function() {
            this.loadGapi();
        }.bind(this));
    }

    loadGapi() {
        // load auth and picker libraries
        if (!frappe.boot.user.google_drive_token) {
            gapi.load('auth', function() {
                this.onAuthApiLoad();
            }.bind(this));
        }

        gapi.load('picker', function() {
            this.onPickerApiLoad();
        }.bind(this));
    }

    onAuthApiLoad() {
        gapi.auth.authorize({
            'client_id': this.clientId,
            'scope': this.scope,
            'immediate': false
        }, function(authResult) {
            this.handleAuthResult(authResult);
        }.bind(this));
    }

    handleAuthResult(authResult) {
        if (authResult && !authResult.error) {
            frappe.boot.user.google_drive_token = authResult.access_token;
            this.createPicker();
        }
    }

    onPickerApiLoad() {
        this.pickerApiLoaded = true;
        this.createPicker();
    }

    createPicker() {
        // Create and render a Picker object for searching images.
        if (this.pickerApiLoaded && frappe.boot.user.google_drive_token) {
            var view = new google.picker.View(google.picker.ViewId.DOCS);
            var picker = new google.picker.PickerBuilder()
                .setAppId(this.appId)
                .setOAuthToken(frappe.boot.user.google_drive_token)
                .addView(view)
                .setDeveloperKey(this.developerKey)
                .setCallback(this.pickerCallback)
                .build();
            picker.setVisible(true);
        }
    }
}
