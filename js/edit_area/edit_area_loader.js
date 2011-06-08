/******
 *
 *	EditArea 
 * 	Developped by Christophe Dolivet
 *	Released under LGPL, Apache and BSD licenses (use the one you want)
 *
******/

function EditAreaLoader(){
	var t=this;
	t.version= "0.8.1.1";
	date= new Date();
	t.start_time=date.getTime();
	t.win= "loading";	// window loading state
	t.error= false;	// to know if load is interrrupt
	t.baseURL="";
	//t.suffix="";
	t.template="";
	t.lang= {};	// array of loaded speech language
	t.load_syntax= {};	// array of loaded syntax language for highlight mode
	t.syntax= {};	// array of initilized syntax language for highlight mode
	t.loadedFiles= [];
	t.waiting_loading= {}; 	// files that must be loaded in order to allow the script to really start
	// scripts that must be loaded in the iframe
	t.scripts_to_load= ["elements_functions", "resize_area", "reg_syntax"];
	t.sub_scripts_to_load= ["edit_area", "manage_area" ,"edit_area_functions", "keyboard", "search_replace", "highlight", "regexp"];
	
	t.resize= []; // contain resizing datas
	t.hidden= {};	// store datas of the hidden textareas
	
	t.default_settings= {
		//id: "src"	// id of the textarea to transform
		debug: false
		,smooth_selection: true
		,font_size: "10"		// not for IE
		,font_family: "monospace"	// can be "verdana,monospace". Allow non monospace font but Firefox get smaller tabulation with non monospace fonts. IE doesn't change the tabulation width and Opera doesn't take this option into account... 
		,start_highlight: false	// if start with highlight
		,toolbar: "search, go_to_line, fullscreen, |, undo, redo, |, select_font,|, change_smooth_selection, highlight, reset_highlight, word_wrap, |, help"
		,begin_toolbar: ""		//  "new_document, save, load, |"
		,end_toolbar: ""		// or end_toolbar
		,is_multi_files: false		// enable the multi file mode (the textarea content is ignored)
		,allow_resize: "both"	// possible values: "no", "both", "x", "y"
		,show_line_colors: false	// if the highlight is disabled for the line currently beeing edited (if enabled => heavy CPU use)
		,min_width: 400
		,min_height: 125
		,replace_tab_by_spaces: false
		,allow_toggle: true		// true or false
		,language: "en"
		,syntax: ""
		,syntax_selection_allow: "basic,brainfuck,c,coldfusion,cpp,css,html,java,js,pas,perl,php,python,ruby,robotstxt,sql,tsql,vb,xml"
		,display: "onload" 		// onload or later
		,max_undo: 30
		,browsers: "known"	// all or known
		,plugins: "" // comma separated plugin list
		,gecko_spellcheck: false	// enable/disable by default the gecko_spellcheck
		,fullscreen: false
		,is_editable: true
		,cursor_position: "begin"
		,word_wrap: false		// define if the text is wrapped of not in the textarea
		,autocompletion: false	// NOT IMPLEMENTED			
		,load_callback: ""		// click on load button (function name)
		,save_callback: ""		// click on save button (function name)
		,change_callback: ""	// textarea onchange trigger (function name)
		,submit_callback: ""	// form submited (function name)
		,EA_init_callback: ""	// EditArea initiliazed (function name)
		,EA_delete_callback: ""	// EditArea deleted (function name)
		,EA_load_callback: ""	// EditArea fully loaded and displayed (function name)
		,EA_unload_callback: ""	// EditArea delete while being displayed (function name)
		,EA_toggle_on_callback: ""	// EditArea toggled on (function name)
		,EA_toggle_off_callback: ""	// EditArea toggled off (function name)
		,EA_file_switch_on_callback: ""	// a new tab is selected (called for the newly selected file)
		,EA_file_switch_off_callback: ""	// a new tab is selected (called for the previously selected file)
		,EA_file_close_callback: ""		// close a tab
	};
	
	t.advanced_buttons = [
			// id, button img, command (it will try to find the translation of "id"), is_file_specific
			['new_document', 'newdocument.gif', 'new_document', false],
			['search', 'search.gif', 'show_search', false],
			['go_to_line', 'go_to_line.gif', 'go_to_line', false],
			['undo', 'undo.gif', 'undo', true],
			['redo', 'redo.gif', 'redo', true],
			['change_smooth_selection', 'smooth_selection.gif', 'change_smooth_selection_mode', true],
			['reset_highlight', 'reset_highlight.gif', 'resync_highlight', true],
			['highlight', 'highlight.gif','change_highlight', true],
			['help', 'help.gif', 'show_help', false],
			['save', 'save.gif', 'save', false],
			['load', 'load.gif', 'load', false],
			['fullscreen', 'fullscreen.gif', 'toggle_full_screen', false],
			['word_wrap', 'word_wrap.gif', 'toggle_word_wrap', true],
			['autocompletion', 'autocompletion.gif', 'toggle_autocompletion', true]
		];
			
	// navigator identification
	t.set_browser_infos(t);

	if(t.isIE>=6 || t.isGecko || ( t.isWebKit && !t.isSafari<3 ) || t.isOpera>=9  || t.isCamino )
		t.isValidBrowser=true;
	else
		t.isValidBrowser=false;

	t.set_base_url();		
	
	for(var i=0; i<t.scripts_to_load.length; i++){
		setTimeout("editAreaLoader.load_script('"+t.baseURL + t.scripts_to_load[i]+ ".js');", 1);	// let the time to Object editAreaLoader to be created before loading additionnal scripts
		t.waiting_loading[t.scripts_to_load[i]+ ".js"]= false;
	}
	t.add_event(window, "load", EditAreaLoader.prototype.window_loaded);
};
	
EditAreaLoader.prototype ={
	has_error : function(){
		this.error= true;
		// set to empty all EditAreaLoader functions
		for(var i in EditAreaLoader.prototype){
			EditAreaLoader.prototype[i]=function(){};		
		}
	},
	
	// add browser informations to the object passed in parameter
	set_browser_infos : function(o){
		ua= navigator.userAgent;
		
		// general detection
		o.isWebKit	= /WebKit/.test(ua);
		o.isGecko	= !o.isWebKit && /Gecko/.test(ua);
		o.isMac		= /Mac/.test(ua);
		
		o.isIE	= (navigator.appName == "Microsoft Internet Explorer");
		if(o.isIE){
			o.isIE = ua.replace(/^.*?MSIE\s+([0-9\.]+).*$/, "$1");
			if(o.isIE<6)
				o.has_error();
		}

		if(o.isOpera = (ua.indexOf('Opera') != -1)){	
			o.isOpera= ua.replace(/^.*?Opera.*?([0-9\.]+).*$/i, "$1");
			if(o.isOpera<9)
				o.has_error();
			o.isIE=false;			
		}

		if(o.isFirefox =(ua.indexOf('Firefox') != -1))
			o.isFirefox = ua.replace(/^.*?Firefox.*?([0-9\.]+).*$/i, "$1");
		// Firefox clones 	
		if( ua.indexOf('Iceweasel') != -1 )
			o.isFirefox	= ua.replace(/^.*?Iceweasel.*?([0-9\.]+).*$/i, "$1");
		if( ua.indexOf('GranParadiso') != -1 )
			o.isFirefox	= ua.replace(/^.*?GranParadiso.*?([0-9\.]+).*$/i, "$1");
		if( ua.indexOf('BonEcho') != -1 )
			o.isFirefox	= ua.replace(/^.*?BonEcho.*?([0-9\.]+).*$/i, "$1");
		if( ua.indexOf('SeaMonkey') != -1)
			o.isFirefox = (ua.replace(/^.*?SeaMonkey.*?([0-9\.]+).*$/i, "$1") ) + 1;
			
		if(o.isCamino =(ua.indexOf('Camino') != -1))
			o.isCamino = ua.replace(/^.*?Camino.*?([0-9\.]+).*$/i, "$1");
			
		if(o.isSafari =(ua.indexOf('Safari') != -1))
			o.isSafari= ua.replace(/^.*?Version\/([0-9]+\.[0-9]+).*$/i, "$1");
	
		if(o.isChrome =(ua.indexOf('Chrome') != -1)) {
			o.isChrome = ua.replace(/^.*?Chrome.*?([0-9\.]+).*$/i, "$1");
			o.isSafari	= false;
		}
		
	},
	
	window_loaded : function(){
		editAreaLoader.win="loaded";
		
		// add events on forms
		if (document.forms) {
			for (var i=0; i<document.forms.length; i++) {
				var form = document.forms[i];
				form.edit_area_replaced_submit=null;
				try {
					
					form.edit_area_replaced_submit = form.onsubmit;
					form.onsubmit="";
				} catch (e) {// Do nothing
				}
				editAreaLoader.add_event(form, "submit", EditAreaLoader.prototype.submit);
				editAreaLoader.add_event(form, "reset", EditAreaLoader.prototype.reset);
			}
		}
		editAreaLoader.add_event(window, "unload", function(){for(var i in editAreas){editAreaLoader.delete_instance(i);}});	// ini callback
	},
	
	// init the checkup of the selection of the IE textarea
	init_ie_textarea : function(id){
		var a=document.getElementById(id);
		try{
			if(a && typeof(a.focused)=="undefined"){
				a.focus();
				a.focused=true;
				a.selectionStart= a.selectionEnd= 0;			
				get_IE_selection(a);
				editAreaLoader.add_event(a, "focus", IE_textarea_focus);
				editAreaLoader.add_event(a, "blur", IE_textarea_blur);
				
			}
		}catch(ex){}
	},
		
	init : function(settings){
		var t=this,s=settings,i;
		
		if(!s["id"])
			t.has_error();
		if(t.error)
			return;
		// if an instance of the editor already exists for this textarea => delete the previous one
		if(editAreas[s["id"]])
			t.delete_instance(s["id"]);
	
		// init settings
		for(i in t.default_settings){
			if(typeof(s[i])=="undefined")
				s[i]=t.default_settings[i];
		}
		
		if(s["browsers"]=="known" && t.isValidBrowser==false){
			return;
		}
		
		if(s["begin_toolbar"].length>0)
			s["toolbar"]= s["begin_toolbar"] +","+ s["toolbar"];
		if(s["end_toolbar"].length>0)
			s["toolbar"]= s["toolbar"] +","+ s["end_toolbar"];
		s["tab_toolbar"]= s["toolbar"].replace(/ /g,"").split(",");
		
		s["plugins"]= s["plugins"].replace(/ /g,"").split(",");
		for(i=0; i<s["plugins"].length; i++){
			if(s["plugins"][i].length==0)
				s["plugins"].splice(i,1);
		}
	//	alert(settings["plugins"].length+": "+ settings["plugins"].join(","));
		t.get_template();
		t.load_script(t.baseURL + "langs/"+ s["language"] + ".js");
		
		if(s["syntax"].length>0){
			s["syntax"]=s["syntax"].toLowerCase();
			t.load_script(t.baseURL + "reg_syntax/"+ s["syntax"] + ".js");
		}
		//alert(this.template);
		
		editAreas[s["id"]]= {"settings": s};
		editAreas[s["id"]]["displayed"]=false;
		editAreas[s["id"]]["hidden"]=false;
		
		//if(settings["display"]=="onload")
		t.start(s["id"]);
	},
	
	// delete an instance of an EditArea
	delete_instance : function(id){
		var d=document,fs=window.frames,span,iframe;
		editAreaLoader.execCommand(id, "EA_delete");
		if(fs["frame_"+id] && fs["frame_"+id].editArea)
		{
			if(editAreas[id]["displayed"])
				editAreaLoader.toggle(id, "off");
			fs["frame_"+id].editArea.execCommand("EA_unload");
		}

		// remove toggle infos and debug textarea
		span= d.getElementById("EditAreaArroundInfos_"+id);
		if(span)
			span.parentNode.removeChild(span);

		// remove the iframe
		iframe= d.getElementById("frame_"+id);
		if(iframe){
			iframe.parentNode.removeChild(iframe);
			//delete iframe;
			try {
				delete fs["frame_"+id];
			} catch (e) {// Do nothing
			}
		}	

		delete editAreas[id];
	},

	
	start : function(id){
		var t=this,d=document,f,span,father,next,html='',html_toolbar_content='',template,content,i;
		
		// check that the window is loaded
		if(t.win!="loaded"){
			setTimeout("editAreaLoader.start('"+id+"');", 50);
			return;
		}
		
		// check that all needed scripts are loaded
		for( i in t.waiting_loading){
			if(t.waiting_loading[i]!="loaded" && typeof(t.waiting_loading[i])!="function"){
				setTimeout("editAreaLoader.start('"+id+"');", 50);
				return;
			}
		}
		
		// wait until language and syntax files are loaded
		if(!t.lang[editAreas[id]["settings"]["language"]] || (editAreas[id]["settings"]["syntax"].length>0 && !t.load_syntax[editAreas[id]["settings"]["syntax"]]) ){
			setTimeout("editAreaLoader.start('"+id+"');", 50);
			return;
		}
		// init the regexp for syntax highlight
		if(editAreas[id]["settings"]["syntax"].length>0)
			t.init_syntax_regexp();
		
			
		// display toggle option and debug area
		if(!d.getElementById("EditAreaArroundInfos_"+id) && (editAreas[id]["settings"]["debug"] || editAreas[id]["settings"]["allow_toggle"]))
		{
			span= d.createElement("span");
			span.id= "EditAreaArroundInfos_"+id;
			if(editAreas[id]["settings"]["allow_toggle"]){
				checked=(editAreas[id]["settings"]["display"]=="onload")?"checked='checked'":"";
				html+="<div id='edit_area_toggle_"+i+"'>";
				html+="<input id='edit_area_toggle_checkbox_"+ id +"' class='toggle_"+ id +"' type='checkbox' onclick='editAreaLoader.toggle(\""+ id +"\");' accesskey='e' "+checked+" />";
				html+="<label for='edit_area_toggle_checkbox_"+ id +"'>{$toggle}</label></div>";	
			}
			if(editAreas[id]["settings"]["debug"])
				html+="<textarea id='edit_area_debug_"+ id +"' spellcheck='off' style='z-index: 20; width: 100%; height: 120px;overflow: auto; border: solid black 1px;'></textarea><br />";				
			html= t.translate(html, editAreas[id]["settings"]["language"]);				
			span.innerHTML= html;				
			father= d.getElementById(id).parentNode;
			next= d.getElementById(id).nextSibling;
			if(next==null)
				father.appendChild(span);
			else
				father.insertBefore(span, next);
		}
		
		if(!editAreas[id]["initialized"])
		{
			t.execCommand(id, "EA_init");	// ini callback
			if(editAreas[id]["settings"]["display"]=="later"){
				editAreas[id]["initialized"]= true;
				return;
			}
		}
		
		if(t.isIE){	// launch IE selection checkup
			t.init_ie_textarea(id);
		}
				
		// get toolbar content
		area=editAreas[id];
		
		for(i=0; i<area["settings"]["tab_toolbar"].length; i++){
		//	alert(this.tab_toolbar[i]+"\n"+ this.get_control_html(this.tab_toolbar[i]));
			html_toolbar_content+= t.get_control_html(area["settings"]["tab_toolbar"][i], area["settings"]["language"]);
		}
		// translate toolbar text here for chrome 2
		html_toolbar_content = t.translate(html_toolbar_content, area["settings"]["language"], "template"); 
		
		
		// create javascript import rules for the iframe if the javascript has not been already loaded by the compressor
		if(!t.iframe_script){
			t.iframe_script="";
			for(i=0; i<t.sub_scripts_to_load.length; i++)
				t.iframe_script+='<script language="javascript" type="text/javascript" src="'+ t.baseURL + t.sub_scripts_to_load[i] +'.js"></script>';
		}
		
		// add plugins scripts if not already loaded by the compressor (but need to load language in all the case)
		for(i=0; i<area["settings"]["plugins"].length; i++){
			//if(typeof(area["settings"]["plugins"][i])=="function") continue;
			if(!t.all_plugins_loaded)
				t.iframe_script+='<script language="javascript" type="text/javascript" src="'+ t.baseURL + 'plugins/' + area["settings"]["plugins"][i] + '/' + area["settings"]["plugins"][i] +'.js"></script>';
			t.iframe_script+='<script language="javascript" type="text/javascript" src="'+ t.baseURL + 'plugins/' + area["settings"]["plugins"][i] + '/langs/' + area["settings"]["language"] +'.js"></script>';
		}
	
		
		// create css link for the iframe if the whole css text has not been already loaded by the compressor
		if(!t.iframe_css){
			t.iframe_css="<link href='"+ t.baseURL +"edit_area.css' rel='stylesheet' type='text/css' />";
		}
		
		
		// create template
		template= t.template.replace(/\[__BASEURL__\]/g, t.baseURL);
		template= template.replace("[__TOOLBAR__]",html_toolbar_content);
			
		
		// fill template with good language sentences
		template= t.translate(template, area["settings"]["language"], "template");
		
		// add css_code
		template= template.replace("[__CSSRULES__]", t.iframe_css);				
		// add js_code
		template= template.replace("[__JSCODE__]", t.iframe_script);
		
		// add version_code
		template= template.replace("[__EA_VERSION__]", t.version);
		//template=template.replace(/\{\$([^\}]+)\}/gm, this.traduc_template);
		
		//editAreas[area["settings"]["id"]]["template"]= template;
		
		area.textarea=d.getElementById(area["settings"]["id"]);
		editAreas[area["settings"]["id"]]["textarea"]=area.textarea;
	
		// if removing previous instances from DOM before (fix from Marcin)
		if(typeof(window.frames["frame_"+area["settings"]["id"]])!='undefined') 
			delete window.frames["frame_"+area["settings"]["id"]];
		
		// insert template in the document after the textarea
		father= area.textarea.parentNode;
	/*	var container= document.createElement("div");
		container.id= "EditArea_frame_container_"+area["settings"]["id"];
	*/	
		content= d.createElement("iframe");
		content.name= "frame_"+area["settings"]["id"];
		content.id= "frame_"+area["settings"]["id"];
		content.style.borderWidth= "0px";
		setAttribute(content, "frameBorder", "0"); // IE
		content.style.overflow="hidden";
		content.style.display="none";

		
		next= area.textarea.nextSibling;
		if(next==null)
			father.appendChild(content);
		else
			father.insertBefore(content, next) ;		
		f=window.frames["frame_"+area["settings"]["id"]];
		f.document.open();
		f.editAreas=editAreas;
		f.area_id= area["settings"]["id"];	
		f.document.area_id= area["settings"]["id"];	
		f.document.write(template);
		f.document.close();

	//	frame.editAreaLoader=this;
		//editAreas[area["settings"]["id"]]["displayed"]=true;
		
	},
	
	toggle : function(id, toggle_to){

	/*	if((editAreas[id]["displayed"]==true  && toggle_to!="on") || toggle_to=="off"){
			this.toggle_off(id);
		}else if((editAreas[id]["displayed"]==false  && toggle_to!="off") || toggle_to=="on"){
			this.toggle_on(id);
		}*/
		if(!toggle_to)
			toggle_to= (editAreas[id]["displayed"]==true)?"off":"on";
		if(editAreas[id]["displayed"]==true  && toggle_to=="off"){
			this.toggle_off(id);
		}else if(editAreas[id]["displayed"]==false  && toggle_to=="on"){
			this.toggle_on(id);
		}
	
		return false;
	},
	
	// static function
	toggle_off : function(id){
		var fs=window.frames,f,t,parNod,nxtSib,selStart,selEnd,scrollTop,scrollLeft;
		if(fs["frame_"+id])
		{	
			f	= fs["frame_"+id];
			t	= editAreas[id]["textarea"];
			if(f.editArea.fullscreen['isFull'])
				f.editArea.toggle_full_screen(false);
			editAreas[id]["displayed"]=false;
			
			// set wrap to off to keep same display mode (some browser get problem with this, so it need more complex operation		
			t.wrap = "off";	// for IE
			setAttribute(t, "wrap", "off");	// for Firefox	
			parNod = t.parentNode;
			nxtSib = t.nextSibling;
			parNod.removeChild(t); 
			parNod.insertBefore(t, nxtSib);
			
			// restore values
			t.value= f.editArea.textarea.value;
			selStart	= f.editArea.last_selection["selectionStart"];
			selEnd		= f.editArea.last_selection["selectionEnd"];
			scrollTop	= f.document.getElementById("result").scrollTop;
			scrollLeft	= f.document.getElementById("result").scrollLeft;
			
			
			document.getElementById("frame_"+id).style.display='none';
		
			t.style.display="inline";

			try{	// IE will give an error when trying to focus an invisible or disabled textarea
				t.focus();
			} catch(e){};
			if(this.isIE){
				t.selectionStart= selStart;
				t.selectionEnd	= selEnd;
				t.focused		= true;
				set_IE_selection(t);
			}else{
				if(this.isOpera && this.isOpera < 9.6 ){	// Opera bug when moving selection start and selection end
					t.setSelectionRange(0, 0);
				}
				try{
					t.setSelectionRange(selStart, selEnd);
				} catch(e) {};
			}
			t.scrollTop= scrollTop;
			t.scrollLeft= scrollLeft;
			f.editArea.execCommand("toggle_off");

		}
	},	
	
	// static function
	toggle_on : function(id){
		var fs=window.frames,f,t,selStart=0,selEnd=0,scrollTop=0,scrollLeft=0,curPos,elem;
			
		if(fs["frame_"+id])
		{
			f	= fs["frame_"+id];
			t	= editAreas[id]["textarea"];
			area= f.editArea;
			area.textarea.value= t.value;
			
			// store display values;
			curPos	= editAreas[id]["settings"]["cursor_position"];

			if(t.use_last==true)
			{
				selStart	= t.last_selectionStart;
				selEnd		= t.last_selectionEnd;
				scrollTop	= t.last_scrollTop;
				scrollLeft	= t.last_scrollLeft;
				t.use_last=false;
			}
			else if( curPos == "auto" )
			{
				try{
					selStart	= t.selectionStart;
					selEnd		= t.selectionEnd;
					scrollTop	= t.scrollTop;
					scrollLeft	= t.scrollLeft;
					//alert(scrollTop);
				}catch(ex){}
			}
			
			// set to good size
			this.set_editarea_size_from_textarea(id, document.getElementById("frame_"+id));
			t.style.display="none";			
			document.getElementById("frame_"+id).style.display="inline";
			area.execCommand("focus"); // without this focus opera doesn't manage well the iframe body height
			
			
			// restore display values
			editAreas[id]["displayed"]=true;
			area.execCommand("update_size");
			
			f.document.getElementById("result").scrollTop= scrollTop;
			f.document.getElementById("result").scrollLeft= scrollLeft;
			area.area_select(selStart, selEnd-selStart);
			area.execCommand("toggle_on");

			
		}
		else
		{
		/*	if(this.isIE)
				get_IE_selection(document.getElementById(id));	*/	
			elem= document.getElementById(id);	
			elem.last_selectionStart= elem.selectionStart;
			elem.last_selectionEnd= elem.selectionEnd;
			elem.last_scrollTop= elem.scrollTop;
			elem.last_scrollLeft= elem.scrollLeft;
			elem.use_last=true;
			editAreaLoader.start(id);
		}
	},	
	
	set_editarea_size_from_textarea : function(id, frame){	
		var elem,width,height;
		elem	= document.getElementById(id);
		
		width	= Math.max(editAreas[id]["settings"]["min_width"], elem.offsetWidth)+"px";
		height	= Math.max(editAreas[id]["settings"]["min_height"], elem.offsetHeight)+"px";
		if(elem.style.width.indexOf("%")!=-1)
			width	= elem.style.width;
		if(elem.style.height.indexOf("%")!=-1)
			height	= elem.style.height;
		//alert("h: "+height+" w: "+width);
	
		frame.style.width= width;
		frame.style.height= height;
	},
		
	set_base_url : function(){
		var t=this,elems,i,docBasePath;

		if( !this.baseURL ){
			elems = document.getElementsByTagName('script');
	
			for( i=0; i<elems.length; i++ ){
				if (elems[i].src && elems[i].src.match(/edit_area_[^\\\/]*$/i) ) {
					var src = elems[i].src;
					src = src.substring(0, src.lastIndexOf('/'));
					this.baseURL = src;
					this.file_name= elems[i].src.substr(elems[i].src.lastIndexOf("/")+1);
					break;
				}
			}
		}
		
		docBasePath	= document.location.href;
		if (docBasePath.indexOf('?') != -1)
			docBasePath	= docBasePath.substring(0, docBasePath.indexOf('?'));
		docBasePath	= docBasePath.substring(0, docBasePath.lastIndexOf('/'));
	
		// If not HTTP absolute
		if (t.baseURL.indexOf('://') == -1 && t.baseURL.charAt(0) != '/') {
			// If site absolute
			t.baseURL = docBasePath + "/" + t.baseURL;
		}
		t.baseURL	+="/";	
	},
	
	get_button_html : function(id, img, exec, isFileSpecific, baseURL) {
		var cmd,html;
		if(!baseURL)
			baseURL= this.baseURL;
		cmd	= 'editArea.execCommand(\'' + exec + '\')';
		html	= '<a id="a_'+ id +'" href="javascript:' + cmd + '" onclick="' + cmd + ';return false;" onmousedown="return false;" target="_self" fileSpecific="'+ (isFileSpecific?'yes':'no') +'">';
		html	+= '<img id="' + id + '" src="'+ baseURL +'images/' + img + '" title="{$' + id + '}" width="20" height="20" class="editAreaButtonNormal" onmouseover="editArea.switchClass(this,\'editAreaButtonOver\');" onmouseout="editArea.restoreClass(this);" onmousedown="editArea.restoreAndSwitchClass(this,\'editAreaButtonDown\');" /></a>';
		return html;
	},

	get_control_html : function(button_name, lang) {		
		var t=this,i,but,html,si;
		for (i=0; i<t.advanced_buttons.length; i++)
		{
			but = t.advanced_buttons[i];			
			if (but[0] == button_name)
			{
				return t.get_button_html(but[0], but[1], but[2], but[3]);
			}	
		}		
				
		switch (button_name){
			case "*":
			case "return":
				return "<br />";
			case "|":
		  	case "separator":
				return '<img src="'+ t.baseURL +'images/spacer.gif" width="1" height="15" class="editAreaSeparatorLine">';
			case "select_font":
				html= "<select id='area_font_size' onchange='javascript:editArea.execCommand(\"change_font_size\")' fileSpecific='yes'>";
				html+="<option value='-1'>{$font_size}</option>";
				si=[8,9,10,11,12,14];
				for( i=0;i<si.length;i++){
					html+="<option value='"+si[i]+"'>"+si[i]+" pt</option>";
				}
				html+="</select>";
				return html;
			case "syntax_selection":
				html= "<select id='syntax_selection' onchange='javascript:editArea.execCommand(\"change_syntax\", this.value)' fileSpecific='yes'>";
				html+="<option value='-1'>{$syntax_selection}</option>";
				html+="</select>";
				return html;
		}
		
		return "<span id='tmp_tool_"+button_name+"'>["+button_name+"]</span>";		
	},
	
	
	get_template : function(){
		if(this.template=="")
		{
			var xhr_object = null; 
			if(window.XMLHttpRequest) // Firefox 
				xhr_object = new XMLHttpRequest(); 
			else if(window.ActiveXObject) // Internet Explorer 
				xhr_object = new ActiveXObject("Microsoft.XMLHTTP"); 
			else { // XMLHttpRequest not supported
				alert("XMLHTTPRequest not supported. EditArea not loaded"); 
				return; 
			} 
			 
			xhr_object.open("GET", this.baseURL+"template.html", false); 
			xhr_object.send(null); 
			if(xhr_object.readyState == 4) 
				this.template=xhr_object.responseText;
			else
				this.has_error();
		}
	},
	
	// translate text
	translate : function(text, lang, mode){
		if(mode=="word")
			text=editAreaLoader.get_word_translation(text, lang);
		else if(mode="template"){
			editAreaLoader.current_language= lang;
			text=text.replace(/\{\$([^\}]+)\}/gm, editAreaLoader.translate_template);
		}
		return text;
	},
	
	translate_template : function(){
		return editAreaLoader.get_word_translation(EditAreaLoader.prototype.translate_template.arguments[1], editAreaLoader.current_language);
	},
	
	get_word_translation : function(val, lang){
		var i;
		
		for( i in editAreaLoader.lang[lang]){
			if(i == val)
				return editAreaLoader.lang[lang][i];
		}
		return "_"+val;
	},
	
	load_script : function(url){
		var t=this,d=document,script,head;
		
		if( t.loadedFiles[url] )
			return;	
		//alert("load: "+url);
		try{
			script= d.createElement("script");
			script.type= "text/javascript";
			script.src= url;
			script.charset= "UTF-8";
			d.getElementsByTagName("head")[0].appendChild(script);
		}catch(e){
			d.write('<sc'+'ript language="javascript" type="text/javascript" src="' + url + '" charset="UTF-8"></sc'+'ript>');
		}
		
		t.loadedFiles[url] = true;
	},
	
	add_event : function(obj, name, handler) {
		try{
			if (obj.attachEvent) {
				obj.attachEvent("on" + name, handler);
			} else{
				obj.addEventListener(name, handler, false);
			}
		}catch(e){}
	},
	
	remove_event : function(obj, name, handler){
		try{
			if (obj.detachEvent)
				obj.detachEvent("on" + name, handler);
			else
				obj.removeEventListener(name, handler, false);
		}catch(e){}
	},


	// reset all the editareas in the form that have been reseted
	reset : function(e){
		var formObj,is_child,i,x;
		
		formObj = editAreaLoader.isIE ? window.event.srcElement : e.target;
		if(formObj.tagName!='FORM')
			formObj= formObj.form;
		
		for( i in editAreas ){			
			is_child= false;
			for( x=0;x<formObj.elements.length;x++ ) {
				if(formObj.elements[x].id == i)
					is_child=true;
			}
			
			if(window.frames["frame_"+i] && is_child && editAreas[i]["displayed"]==true){
			
				var exec= 'window.frames["frame_'+ i +'"].editArea.textarea.value= document.getElementById("'+ i +'").value;';
				exec+= 'window.frames["frame_'+ i +'"].editArea.execCommand("focus");';
				exec+= 'window.frames["frame_'+ i +'"].editArea.check_line_selection();';
				exec+= 'window.frames["frame_'+ i +'"].editArea.execCommand("reset");';
				window.setTimeout(exec, 10);
			}
		}		
		return;
	},
	
	
	// prepare all the textarea replaced by an editarea to be submited
	submit : function(e){		
		var formObj,is_child,fs=window.frames,i,x;
		formObj = editAreaLoader.isIE ? window.event.srcElement : e.target;
		if(formObj.tagName!='FORM')
			formObj= formObj.form;
		
		for( i in editAreas){
			is_child= false;
			for( x=0;x<formObj.elements.length;x++ ) {
				if(formObj.elements[x].id == i)
					is_child=true;
			}
		
			if(is_child)
			{
				if(fs["frame_"+i] && editAreas[i]["displayed"]==true)
					document.getElementById(i).value= fs["frame_"+ i].editArea.textarea.value;
				editAreaLoader.execCommand(i,"EA_submit");
			}
		}				
		if( typeof(formObj.edit_area_replaced_submit) == "function" ){
			res= formObj.edit_area_replaced_submit();
			if(res==false){
				if(editAreaLoader.isIE)
					return false;
				else
					e.preventDefault();
			}
		}
		return;
	},
	
	// allow to get the value of the editarea
	getValue : function(id){
        if(window.frames["frame_"+id] && editAreas[id]["displayed"]==true){
            return window.frames["frame_"+ id].editArea.textarea.value;       
        }else if(elem=document.getElementById(id)){
        	return elem.value;
        }
        return false;
    },
    
    // allow to set the value of the editarea
    setValue : function(id, new_val){
    	var fs=window.frames;
    	
        if( ( f=fs["frame_"+id] ) && editAreas[id]["displayed"]==true){
			f.editArea.textarea.value= new_val;     
			f.editArea.execCommand("focus"); 
			f.editArea.check_line_selection(false);  
			f.editArea.execCommand("onchange");
        }else if(elem=document.getElementById(id)){
        	elem.value= new_val;
        }
    },
	    
    // allow to get infos on the selection: array(start, end)
    getSelectionRange : function(id){
    	var sel,eA,fs=window.frames;
    	
    	sel= {"start": 0, "end": 0};
        if(fs["frame_"+id] && editAreas[id]["displayed"]==true){
        	eA= fs["frame_"+ id].editArea;

			sel["start"]	= eA.textarea.selectionStart;
			sel["end"]		= eA.textarea.selectionEnd;
		
        }else if( elem=document.getElementById(id) ){
        	sel= getSelectionRange(elem);
        }
        return sel;
    },
    
    // allow to set the selection with the given start and end positions
    setSelectionRange : function(id, new_start, new_end){
    	var fs=window.frames;
    	
        if(fs["frame_"+id] && editAreas[id]["displayed"]==true){
            fs["frame_"+ id].editArea.area_select(new_start, new_end-new_start);  
			// make an auto-scroll to the selection
			if(!this.isIE){
				fs["frame_"+ id].editArea.check_line_selection(false); 
				fs["frame_"+ id].editArea.scroll_to_view();
			}   
        }else if(elem=document.getElementById(id)){
        	setSelectionRange(elem, new_start, new_end);
        }
    },
    
    getSelectedText : function(id){
    	var sel= this.getSelectionRange(id);
    	
        return this.getValue(id).substring(sel["start"], sel["end"]);
    },
	
	setSelectedText : function(id, new_val){
		var fs=window.frames,d=document,sel,text,scrollTop,scrollLeft,new_sel_end;
		
		new_val	= new_val.replace(/\r/g, ""); 
		sel		= this.getSelectionRange(id);
		text	= this.getValue(id);
		if(fs["frame_"+id] && editAreas[id]["displayed"]==true){
			scrollTop	= fs["frame_"+ id].document.getElementById("result").scrollTop;
			scrollLeft	= fs["frame_"+ id].document.getElementById("result").scrollLeft;
		}else{
			scrollTop	= d.getElementById(id).scrollTop;
			scrollLeft	= d.getElementById(id).scrollLeft;
		}
		
		text	= text.substring(0, sel["start"])+ new_val +text.substring(sel["end"]);
		this.setValue(id, text);
		new_sel_end	= sel["start"]+ new_val.length;
		this.setSelectionRange(id, sel["start"], new_sel_end);
		
		
		// fix \r problem for selection length count on IE & Opera
		if(new_val != this.getSelectedText(id).replace(/\r/g, "")){
			this.setSelectionRange(id, sel["start"], new_sel_end+ new_val.split("\n").length -1);
		}
		// restore scrolling position
		if(fs["frame_"+id] && editAreas[id]["displayed"]==true){
			fs["frame_"+ id].document.getElementById("result").scrollTop= scrollTop;
			fs["frame_"+ id].document.getElementById("result").scrollLeft= scrollLeft;
			fs["frame_"+ id].editArea.execCommand("onchange");
		}else{
			d.getElementById(id).scrollTop= scrollTop;
			d.getElementById(id).scrollLeft= scrollLeft;
		}
    },
    
    insertTags : function(id, open_tag, close_tag){
    	var old_sel,new_sel;
    	
    	old_sel	= this.getSelectionRange(id);
    	text	= open_tag + this.getSelectedText(id) + close_tag;
    	 
		editAreaLoader.setSelectedText(id, text);
		
    	new_sel	= this.getSelectionRange(id);
    	if(old_sel["end"] > old_sel["start"])	// if text was selected, cursor at the end
    		this.setSelectionRange(id, new_sel["end"], new_sel["end"]);
    	else // cursor in the middle
    		this.setSelectionRange(id, old_sel["start"]+open_tag.length, old_sel["start"]+open_tag.length);
    },
    
    // hide both EditArea and normal textarea
	hide : function(id){
		var fs= window.frames,d=document,t=this,scrollTop,scrollLeft,span;
		if(d.getElementById(id) && !t.hidden[id])
		{
			t.hidden[id]= {};
			t.hidden[id]["selectionRange"]= t.getSelectionRange(id);
			if(d.getElementById(id).style.display!="none")
			{
				t.hidden[id]["scrollTop"]= d.getElementById(id).scrollTop;
				t.hidden[id]["scrollLeft"]= d.getElementById(id).scrollLeft;
			}
					
			if(fs["frame_"+id])
			{
				t.hidden[id]["toggle"]= editAreas[id]["displayed"];
				
				if(fs["frame_"+id] && editAreas[id]["displayed"]==true){
					scrollTop	= fs["frame_"+ id].document.getElementById("result").scrollTop;
					scrollLeft	= fs["frame_"+ id].document.getElementById("result").scrollLeft;
				}else{
					scrollTop	= d.getElementById(id).scrollTop;
					scrollLeft	= d.getElementById(id).scrollLeft;
				}
				t.hidden[id]["scrollTop"]= scrollTop;
				t.hidden[id]["scrollLeft"]= scrollLeft;
				
				if(editAreas[id]["displayed"]==true)
					editAreaLoader.toggle_off(id);
			}
			
			// hide toggle button and debug box
			span= d.getElementById("EditAreaArroundInfos_"+id);
			if(span){
				span.style.display='none';
			}
			
			// hide textarea
			d.getElementById(id).style.display= "none";
		}
	},
	
	// restore hidden EditArea and normal textarea
	show : function(id){
		var fs= window.frames,d=document,t=this,span;
		if((elem=d.getElementById(id)) && t.hidden[id])
		{
			elem.style.display= "inline";
			elem.scrollTop= t.hidden[id]["scrollTop"];
			elem.scrollLeft= t.hidden[id]["scrollLeft"];
			span= d.getElementById("EditAreaArroundInfos_"+id);
			if(span){
				span.style.display='inline';
			}
			
			if(fs["frame_"+id])
			{
								
				// restore toggle button and debug box
			
				
				// restore textarea
				elem.style.display= "inline";
				
				// restore EditArea
				if(t.hidden[id]["toggle"]==true)
					editAreaLoader.toggle_on(id);
				
				scrollTop	= t.hidden[id]["scrollTop"];
				scrollLeft	= t.hidden[id]["scrollLeft"];
				
				if(fs["frame_"+id] && editAreas[id]["displayed"]==true){
					fs["frame_"+ id].document.getElementById("result").scrollTop	= scrollTop;
					fs["frame_"+ id].document.getElementById("result").scrollLeft	= scrollLeft;
				}else{
					elem.scrollTop	= scrollTop;
					elem.scrollLeft	= scrollLeft;
				}
			
			}
			// restore selection
			sel	= t.hidden[id]["selectionRange"];
			t.setSelectionRange(id, sel["start"], sel["end"]);
			delete t.hidden[id];	
		}
	},
	
	// get the current file datas (for multi file editing mode)
	getCurrentFile : function(id){
		return this.execCommand(id, 'get_file', this.execCommand(id, 'curr_file'));
	},
	
	// get the given file datas (for multi file editing mode)
	getFile : function(id, file_id){
		return this.execCommand(id, 'get_file', file_id);
	},
	
	// get all the openned files datas (for multi file editing mode)
	getAllFiles : function(id){
		return this.execCommand(id, 'get_all_files()');
	},
	
	// open a file (for multi file editing mode)
	openFile : function(id, file_infos){
		return this.execCommand(id, 'open_file', file_infos);
	},
	
	// close the given file (for multi file editing mode)
	closeFile : function(id, file_id){
		return this.execCommand(id, 'close_file', file_id);
	},
	
	// close the given file (for multi file editing mode)
	setFileEditedMode : function(id, file_id, to){
		var reg1,reg2;
		reg1	= new RegExp('\\\\', 'g');
		reg2	= new RegExp('"', 'g');
		return this.execCommand(id, 'set_file_edited_mode("'+ file_id.replace(reg1, '\\\\').replace(reg2, '\\"') +'", '+ to +')');
	},
	
	
	// allow to access to editarea functions and datas (for advanced users only)
	execCommand : function(id, cmd, fct_param){
		switch(cmd){
			case "EA_init":
				if(editAreas[id]['settings']["EA_init_callback"].length>0)
					eval(editAreas[id]['settings']["EA_init_callback"]+"('"+ id +"');");
				break;
			case "EA_delete":
				if(editAreas[id]['settings']["EA_delete_callback"].length>0)
					eval(editAreas[id]['settings']["EA_delete_callback"]+"('"+ id +"');");
				break;
			case "EA_submit":
				if(editAreas[id]['settings']["submit_callback"].length>0)
					eval(editAreas[id]['settings']["submit_callback"]+"('"+ id +"');");
				break;
		}
        if(window.frames["frame_"+id] && window.frames["frame_"+ id].editArea){
			if(fct_param!=undefined)
				return eval('window.frames["frame_'+ id +'"].editArea.'+ cmd +'(fct_param);');
			else
				return eval('window.frames["frame_'+ id +'"].editArea.'+ cmd +';');       
        }
        return false;
    }
};
	
	var editAreaLoader= new EditAreaLoader();
	var editAreas= {};

