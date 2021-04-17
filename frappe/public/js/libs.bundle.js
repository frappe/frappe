import "bootstrap/dist/js/bootstrap.bundle.js";
import Vue from "vue/dist/vue.esm.js";
import moment from "moment/min/moment-with-locales.js";
import momentTimezone from "moment-timezone/builds/moment-timezone-with-data.js";
import "socket.io-client/dist/socket.io.slim.js";
import "./lib/Sortable.min.js";
import "./lib/jquery/jquery.hotkeys.js";
import "./lib/jSignature.min.js";

window.moment = momentTimezone;
window.Vue = Vue;
