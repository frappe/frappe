/*
 * Author: Alex Gibson
 * https://github.com/alexgibson/notify.js
 * License: MIT license
 */

(function(global, factory) {
    if (typeof define === 'function' && define.amd) {
        // AMD environment
        define(function() {
            return factory(global, global.document);
        });
    } else if (typeof module !== 'undefined' && module.exports) {
        // CommonJS environment
        module.exports = factory(global, global.document);
    } else {
        // Browser environment
        global.Notify = factory(global, global.document);
    }
} (typeof window !== 'undefined' ? window : this, function (w, d) {

    'use strict';

    function isFunction (item) {
        return typeof item === 'function';
    }

    function Notify(title, options) {

        if (typeof title !== 'string') {
            throw new Error('Notify(): first arg (title) must be a string.');
        }

        this.title = title;

        this.options = {
            icon: '',
            body: '',
            tag: '',
            notifyShow: null,
            notifyClose: null,
            notifyClick: null,
            notifyError: null,
            timeout: null
        };

        this.permission = null;

        if (!Notify.isSupported) {
            return;
        }

        //User defined options for notification content
        if (typeof options === 'object') {

            for (var i in options) {
                if (options.hasOwnProperty(i)) {
                    this.options[i] = options[i];
                }
            }

            //callback when notification is displayed
            if (isFunction(this.options.notifyShow)) {
                this.onShowCallback = this.options.notifyShow;
            }

            //callback when notification is closed
            if (isFunction(this.options.notifyClose)) {
                this.onCloseCallback = this.options.notifyClose;
            }

            //callback when notification is clicked
            if (isFunction(this.options.notifyClick)) {
                this.onClickCallback = this.options.notifyClick;
            }

            //callback when notification throws error
            if (isFunction(this.options.notifyError)) {
                this.onErrorCallback = this.options.notifyError;
            }
        }
    }

    // true if the browser supports HTML5 Notification
    Notify.isSupported = 'Notification' in w;

    // true if the permission is not granted
    Notify.needsPermission = !(Notify.isSupported && Notification.permission === 'granted');

    // returns current permission level ('granted', 'default', 'denied' or null)
    Notify.permissionLevel = (Notify.isSupported ? Notification.permission : null);

    // asks the user for permission to display notifications.  Then calls the callback functions is supplied.
    Notify.requestPermission = function (onPermissionGrantedCallback, onPermissionDeniedCallback) {
        if (!Notify.isSupported) {
            return;
        }
        w.Notification.requestPermission(function (perm) {
            switch (perm) {
                case 'granted':
                    Notify.needsPermission = false;
                    if (isFunction(onPermissionGrantedCallback)) {
                        onPermissionGrantedCallback();
                    }
                    break;
                case 'denied':
                    if (isFunction(onPermissionDeniedCallback)) {
                        onPermissionDeniedCallback();
                    }
                    break;
            }
        });
    };


    Notify.prototype.show = function () {

        if (!Notify.isSupported) {
            return;
        }

        this.myNotify = new Notification(this.title, {
            'body': this.options.body,
            'tag' : this.options.tag,
            'icon' : this.options.icon
        });

        if (this.options.timeout && !isNaN(this.options.timeout)) {
            setTimeout(this.close.bind(this), this.options.timeout * 1000);
        }

        this.myNotify.addEventListener('show', this, false);
        this.myNotify.addEventListener('error', this, false);
        this.myNotify.addEventListener('close', this, false);
        this.myNotify.addEventListener('click', this, false);
    };

    Notify.prototype.onShowNotification = function (e) {
        if (this.onShowCallback) {
            this.onShowCallback(e);
        }
    };

    Notify.prototype.onCloseNotification = function (e) {
        if (this.onCloseCallback) {
            this.onCloseCallback(e);
        }
        this.destroy();
    };

    Notify.prototype.onClickNotification = function (e) {
        if (this.onClickCallback) {
            this.onClickCallback(e);
        }
    };

    Notify.prototype.onErrorNotification = function (e) {
        if (this.onErrorCallback) {
            this.onErrorCallback(e);
        }
        this.destroy();
    };

    Notify.prototype.destroy = function () {
        this.myNotify.removeEventListener('show', this, false);
        this.myNotify.removeEventListener('error', this, false);
        this.myNotify.removeEventListener('close', this, false);
        this.myNotify.removeEventListener('click', this, false);
    };

    Notify.prototype.close = function () {
        this.myNotify.close();
    };

    Notify.prototype.handleEvent = function (e) {
        switch (e.type) {
        case 'show':
            this.onShowNotification(e);
            break;
        case 'close':
            this.onCloseNotification(e);
            break;
        case 'click':
            this.onClickNotification(e);
            break;
        case 'error':
            this.onErrorNotification(e);
            break;
        }
    };

    return Notify;

}));
