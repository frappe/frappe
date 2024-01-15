import * as React from "react";
import { App } from "./App";
import { createRoot } from "react-dom/client";

class WhiteboardEditor {
  constructor({ wrapper }) {
    this.$wrapper = $(wrapper);

    this.init();
  }

  init() {
    this.setup_app();
  }

  setup_app() {
    // create and mount the react app
    const root = createRoot(this.$wrapper.get(0));
    root.render(<App />);
    this.$whiteboard = root;
  }
}

frappe.provide("frappe.ui");
frappe.ui.WhiteboardEditor = WhiteboardEditor;
export default WhiteboardEditor;
