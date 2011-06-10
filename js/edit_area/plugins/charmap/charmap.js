/**
 * Charmap plugin
 * by Christophe Dolivet
 * v0.1 (2006/09/22)
 * 
 *    
 * This plugin allow to use a visual keyboard allowing to insert any UTF-8 characters in the text.
 * 
 * - plugin name to add to the plugin list: "charmap"
 * - plugin name to add to the toolbar list: "charmap" 
 * - possible parameters to add to EditAreaLoader.init(): 
 * 		"charmap_default": (String) define the name of the default character range displayed on popup display
 * 							(default: "arrows")
 * 
 * 
 */
   
var EditArea_charmap= {
	/**
	 * Get called once this file is loaded (editArea still not initialized)
	 *
	 * @return nothing	 
	 */	 	 	
	init: function(){	
		this.default_language="Arrows";
	}
	
	/**
	 * Returns the HTML code for a specific control string or false if this plugin doesn't have that control.
	 * A control can be a button, select list or any other HTML item to present in the EditArea user interface.
	 * Language variables such as {$lang_somekey} will also be replaced with contents from
	 * the language packs.
	 * 
	 * @param {string} ctrl_name: the name of the control to add	  
	 * @return HTML code for a specific control or false.
	 * @type string	or boolean
	 */	
	,get_control_html: function(ctrl_name){
		switch(ctrl_name){
			case "charmap":
				// Control id, button img, command
				return parent.editAreaLoader.get_button_html('charmap_but', 'charmap.gif', 'charmap_press', false, this.baseURL);
		}
		return false;
	}
	/**
	 * Get called once EditArea is fully loaded and initialised
	 *	 
	 * @return nothing
	 */	 	 	
	,onload: function(){ 
		if(editArea.settings["charmap_default"] && editArea.settings["charmap_default"].length>0)
			this.default_language= editArea.settings["charmap_default"];
	}
	
	/**
	 * Is called each time the user touch a keyboard key.
	 *	 
	 * @param (event) e: the keydown event
	 * @return true - pass to next handler in chain, false - stop chain execution
	 * @type boolean	 
	 */
	,onkeydown: function(e){
		
	}
	
	/**
	 * Executes a specific command, this function handles plugin commands.
	 *
	 * @param {string} cmd: the name of the command being executed
	 * @param {unknown} param: the parameter of the command	 
	 * @return true - pass to next handler in chain, false - stop chain execution
	 * @type boolean	
	 */
	,execCommand: function(cmd, param){
		// Handle commands
		switch(cmd){
			case "charmap_press":
				win= window.open(this.baseURL+"popup.html", "charmap", "width=500,height=270,scrollbars=yes,resizable=yes");
				win.focus();
				return false;
		}
		// Pass to next handler in chain
		return true;
	}
	
};

// Adds the plugin class to the list of available EditArea plugins
editArea.add_plugin("charmap", EditArea_charmap);
