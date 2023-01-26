import "./jquery-bootstrap";
import "./lib/moment";
import Sortable from "sortablejs";

window.SetVueGlobals = (app) => {
	app.config.globalProperties.__ = window.__;
	app.config.globalProperties.frappe = window.frappe;
};
window.Sortable = Sortable;
