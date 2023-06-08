import "./jquery-bootstrap";
import "./lib/moment";
import "../js/lib/leaflet/leaflet.js";
import "../js/lib/leaflet_easy_button/easy-button.js";
import "../js/lib/leaflet_draw/leaflet.draw.js";
import "../js/lib/leaflet_control_locate/L.Control.Locate.js";
import Sortable from "sortablejs";

window.SetVueGlobals = (app) => {
	app.config.globalProperties.__ = window.__;
	app.config.globalProperties.frappe = window.frappe;
};
window.Sortable = Sortable;
