import { defineStore } from "pinia";
export const useMainStore = defineStore("useMainStore", {
	state: () => ({
		/**
		 * @type {'mouse-pointer'|'text'|'rectangle'|'image'|'components'|'table'|'barcode'}  activeControl
		 * @type {'static'|'dynamic'}  textControlType
		 */
		activeControl: "mouse-pointer",
		textControlType: "dynamic",
		mainContainer: new Object(),
		propertiesContainer: new Object(),
		metaFields: [],
		dynamicData: [],
		snapPoints: [],
		snapEdges: [],
		doctype: null,
		currentDoc: null,
		imageDocFields: [],
		selectCurrentDocDialog: null,
		docData: [],
		openModal: false,
		openDyanmicModal: null,
		openTableModal: null,
		openImageModal: null,
		isMoveStart: false,
		isDrawing: false,
		isDropped: false,
		isAltKey: false,
		isShiftKey: false,
		lastCloned: null,
		currentDrawListener: null,
		isMoved: false,
		bodyElement: null,
		currentPageSize: "A4",
		pageSizes: null,
		lastCreatedElement: null,
		screenStyleSheet: null,
		printStyleSheet: null,
		printCssVariableID: null,
		printCssVariables: null,
		isMarqueeActive: false,
		modal: null,
		modalLocation: {
			isDragged: false,
			x: 0,
			y: 0,
		},
		toolbarWidth: 44,
		currentElements: {},
		globalStyles: {
			staticText: new Object({
				styles: {
					display: "inline-block",
					fontFamily: "Inter",
					fontSize: "14px",
					fontWeight: 400,
					color: "#000000",
					textAlign: "left",
					fontStyle: "normal",
					textDecoration: "none",
					textTransform: "none",
					lineHeight: 1.25,
					letterSpacing: 0,
					contenteditable: false,
					border: "none",
					borderTopWidth: "",
					borderBottomWidth: "",
					borderLeftWidth: "",
					borderRightWidth: "",
					borderRadius: 0,
					backgroundColor: "",
					padding: "0px",
					margin: "0px",
					minWidth: "0px",
					minHeight: "0px",
					boxShadow: "none",
					overflow: "hidden",
					overflowWrap: "break-word",
					userSelect: "none",
					opacity: 1,
					zIndex: 1,
				},
			}),
			dynamicText: new Object({
				styles: {
					display: "inline",
					fontFamily: "Inter",
					fontSize: "14px",
					fontWeight: 400,
					color: "#000000",
					textAlign: "left",
					fontStyle: "normal",
					textDecoration: "none",
					textTransform: "none",
					lineHeight: 1.25,
					letterSpacing: 0,
					contenteditable: false,
					border: "none",
					borderTopWidth: "",
					borderBottomWidth: "",
					borderLeftWidth: "",
					borderRightWidth: "",
					borderRadius: 0,
					backgroundColor: "",
					padding: "0px",
					margin: "0px",
					minWidth: "0px",
					minHeight: "0px",
					boxShadow: "none",
					overflowWrap: "break-word",
					userSelect: "none",
					opacity: 1,
				},
			}),
			rectangle: new Object({
				styles: {
					display: "inline-flex",
					justifyContent: "flex-start",
					alignItems: "flex-start",
					alignContent: "flex-start",
					flex: 1,
					padding: "0px",
					margin: "0px",
					userSelect: "none",
					minWidth: "0px",
					minHeight: "0px",
					color: "#000000",
					backgroundColor: "transperant",
					border: "1px solid black",
					boxSizing: "border-box",
					outline: "none",
					borderRadius: 0,
					boxShadow: "none",
					opacity: 1,
					zIndex: 0,
				},
			}),
			image: new Object({
				styles: {
					display: "block",
					border: "none",
					borderTopWidth: "",
					borderBottomWidth: "",
					borderLeftWidth: "",
					borderRightWidth: "",
					borderRadius: 0,
					backgroundColor: "",
					padding: "0px",
					margin: "0px",
					minWidth: "0px",
					minHeight: "0px",
					boxShadow: "none",
					userSelect: "none",
					objectFit: "scale-down",
					objectPosition: "center center",
					opacity: 1,
				},
			}),
			table: new Object({
				styles: {
					fontFamily: "Inter",
					fontSize: "18px",
					fontWeight: 400,
					color: "#000000",
					textAlign: "left",
					fontStyle: "normal",
					textDecoration: "none",
					textTransform: "none",
					lineHeight: 1.25,
					letterSpacing: 0,
					contenteditable: false,
					border: "none",
					borderTopWidth: "",
					borderBottomWidth: "",
					borderLeftWidth: "",
					borderRightWidth: "",
					borderRadius: 0,
					backgroundColor: "white",
					padding: "0px",
					margin: "0px",
					minWidth: "0px",
					minHeight: "0px",
					boxShadow: "none",
					overflowWrap: "break-word",
					userSelect: "none",
					opacity: 1,
				},
			}),
		},
		cursor: "default",
		print_design_name: "",
		propertiesmodal: {
			selected_doctype: "",
		},
		isLayerPanelEnabled: false,
		page: {
			height: 297,
			width: 210,
			marginTop: 4.2,
			marginBottom: 4.2,
			marginLeft: 3,
			marginRight: 3,
			UOM: "mm",
		},
		controls: {
			MousePointer: {
				icon: "fa fa-mouse-pointer",
				control: "MousePointer",
				aria_label: __("Mouse Pointer (M)"),
				id: "mouse-pointer",
				cursor: "default",
			},
			Text: {
				icon: "fa fa-font",
				control: "Text",
				aria_label: "Text (T)",
				id: "text",
				cursor: "text",
			},
			Rectangle: {
				icon: "fa fa-square-o",
				control: "Rectangle",
				aria_label: "Rectangle (R)",
				id: "rectangle",
				cursor: "crosshair",
			},
			Components: {
				icon: "fa fa-cube",
				control: "Components",
				aria_label: "Components (C)",
				id: "components",
				cursor: "default",
			},
			Image: {
				icon: "fa fa-image",
				control: "Image",
				aria_label: "Image (I)",
				id: "image",
				cursor: "crosshair",
			},
			Table: {
				icon: "fa fa-table",
				control: "Table",
				aria_label: "Table (A)",
				id: "table",
				cursor: "crosshair",
			},
			Barcode: {
				icon: "fa fa-barcode",
				control: "Barcode",
				aria_label: "Barcode (B)",
				id: "barcode",
				cursor: "crosshair",
			},
		},
	}),
	getters: {
		getPageSettings() {
			return {
				height:
					this.page.height -
					(this.page.marginTop + this.page.marginBottom) +
					this.page.UOM,
				width:
					this.page.width -
					(this.page.marginLeft + this.page.marginRight) +
					this.page.UOM,
			};
		},
		getMarginElement() {
			return {
				height: this.page.height + this.page.UOM,
				width: this.page.width + this.page.UOM,
			};
		},
		getCurrentElementsValues() {
			return Object.values(this.currentElements);
		},
		getCurrentElementsId() {
			return Object.keys(this.currentElements);
		},
		getLinkMetaFields: (state) => {
			return state.metaFields
				.filter((el) => el.fieldtype == "Link")
				.sort((a, b) => a.label.localeCompare(b.label));
		},
		getTableMetaFields: (state) => {
			return state.metaFields.filter((el) => el.fieldtype == "Table");
		},
		getTypeWiseMetaFields: (state) => {
			return (selectedParentField) => {
				let fields = {};
				let metaFields = state.metaFields;
				if (selectedParentField) {
					metaFields = metaFields.find(
						(e) => e.fieldname === selectedParentField
					).childfields;
				}
				metaFields.forEach((field) => {
					if (
						[
							"Link",
							"Button",
							"Color",
							"Table",
							"Image",
							"Attach",
							"Attach Image",
							"Table",
						].indexOf(field.fieldtype) == -1
					) {
						if (fields[field.fieldtype]) {
							fields[field.fieldtype].push(field);
						} else {
							fields[field.fieldtype] = [field];
						}
					}
				});
				console.log(fields);
				return fields;
			};
		},
	},
	actions: {
		/**
		 * @param {'MousePointer'|'Text'|'Rectangle'|'Components'|'Image'|'Table'|'Barcode'}  id
		 */
		setActiveControl(id) {
			let control = this.controls[id];
			this.activeControl = control.id;
			this.cursor = control.cursor;
		},
		setPrintDesignName(name) {
			this.print_design_name = name;
		},
		setPropertiesModal(data) {
			this.propertiesmodal.selected_doctype = data["selected_doctype"];
		},
		/**
		 * @param {Array} rules Accepts an array of JSON-encoded declarations
		 * @return {String} Id of CssRule
		 * @example
		addStylesheetRules([
		['h2', // Also accepts a second argument as an array of arrays instead
			['color', 'red'],
			['background-color', 'green', true] // 'true' for !important rules
		],
		['.myClass',
			['background-color', 'yellow']
		]
		]);
		*/
		addStylesheetRules(rules, media = "screen") {
			for (let i = 0; i < rules.length; i++) {
				let j = 1,
					rule = rules[i],
					selector = rule[0],
					propStr = "";
				// If the second argument of a rule is an array of arrays, correct our variables.
				if (Array.isArray(rule[1][0])) {
					rule = rule[1];
					j = 0;
				}

				for (let pl = rule.length; j < pl; j++) {
					const prop = rule[j];
					prop[0] = prop[0]
						.replace(/([a-z])([A-Z])/g, "$1-$2")
						.replace(/[\s_]+/g, "-")
						.toLowerCase();
					propStr += `${prop[0]}: ${prop[1]}${prop[2] ? " !important" : ""};\n`;
				}

				// Insert CSS Rule
				if (media == "screen") {
					return this.screenStyleSheet.insertRule(
						`${selector}{${propStr}}`,
						this.screenStyleSheet.cssRules.length
					);
				} else {
					return this.printStyleSheet.insertRule(
						`${selector}{${propStr}}`,
						this.printStyleSheet.cssRules.length
					);
				}
			}
		},
		/**
		 * @param {('rectangle'|'staticText'|'dynamicText'|'image'|'table')} type Add globalStyles for your print designs
		 **/
		addGlobalRules(type = "all") {
			if (type == "all") {
				Object.entries(this.globalStyles).forEach((element) => {
					let type = element[0];
					let styles = element[1].styles;
					const id = this.addStylesheetRules([
						[`.${type}`, [...Object.entries(styles)]],
					]);
					this.globalStyles[type].cssRule = this.screenStyleSheet.cssRules[id];
				});
			} else {
				const id = this.addStylesheetRules([
					[`.${type}`, [...Object.entries(this.globalStyles[type].styles)]],
				]);
				this.globalStyles[type].cssRule = this.screenStyleSheet.cssRules[id];
			}
		},
	},
});
