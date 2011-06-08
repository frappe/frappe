/******
 *
 *	EditArea 
 * 	Developped by Christophe Dolivet
 *	Released under LGPL, Apache and BSD licenses (use the one you want)
 *
******/

	function EditArea(){
		var t=this;
		t.error= false;	// to know if load is interrrupt
		
		t.inlinePopup= [{popup_id: "area_search_replace", icon_id: "search"},
									{popup_id: "edit_area_help", icon_id: "help"}];
		t.plugins= {};
	
		t.line_number=0;
		
		parent.editAreaLoader.set_browser_infos(t); 	// navigator identification
		// fix IE8 detection as we run in IE7 emulate mode through X-UA <meta> tag
		if( t.isIE >= 8 )
			t.isIE	= 7;
		
		t.last_selection={};		
		t.last_text_to_highlight="";
		t.last_hightlighted_text= "";
		t.syntax_list= [];
		t.allready_used_syntax= {};
		t.check_line_selection_timer= 50;	// the timer delay for modification and/or selection change detection
		
		t.textareaFocused= false;
		t.highlight_selection_line= null;
		t.previous= [];
		t.next= [];
		t.last_undo="";
		t.files= {};
		t.filesIdAssoc= {};
		t.curr_file= '';
		//t.loaded= false;
		t.assocBracket={};
		t.revertAssocBracket= {};		
		// bracket selection init 
		t.assocBracket["("]=")";
		t.assocBracket["{"]="}";
		t.assocBracket["["]="]";		
		for(var index in t.assocBracket){
			t.revertAssocBracket[t.assocBracket[index]]=index;
		}
		t.is_editable= true;
		
		
		/*t.textarea="";	
		
		t.state="declare";
		t.code = []; // store highlight syntax for languagues*/
		// font datas
		t.lineHeight= 16;
		/*t.default_font_family= "monospace";
		t.default_font_size= 10;*/
		t.tab_nb_char= 8;	//nb of white spaces corresponding to a tabulation
		if(t.isOpera)
			t.tab_nb_char= 6;

		t.is_tabbing= false;
		
		t.fullscreen= {'isFull': false};
		
		t.isResizing=false;	// resize var
		
		// init with settings and ID (area_id is a global var defined by editAreaLoader on iframe creation
		t.id= area_id;
		t.settings= editAreas[t.id]["settings"];
		
		if((""+t.settings['replace_tab_by_spaces']).match(/^[0-9]+$/))
		{
			t.tab_nb_char= t.settings['replace_tab_by_spaces'];
			t.tabulation="";
			for(var i=0; i<t.tab_nb_char; i++)
				t.tabulation+=" ";
		}else{
			t.tabulation="\t";
		}
			
		// retrieve the init parameter for syntax
		if(t.settings["syntax_selection_allow"] && t.settings["syntax_selection_allow"].length>0)
			t.syntax_list= t.settings["syntax_selection_allow"].replace(/ /g,"").split(",");
		
		if(t.settings['syntax'])
			t.allready_used_syntax[t.settings['syntax']]=true;
		
		
	};
	EditArea.prototype.init= function(){
		var t=this, a, s=t.settings;
		t.textarea			= _$("textarea");
		t.container			= _$("container");
		t.result			= _$("result");
		t.content_highlight	= _$("content_highlight");
		t.selection_field	= _$("selection_field");
		t.selection_field_text= _$("selection_field_text");
		t.processing_screen	= _$("processing");
		t.editor_area		= _$("editor");
		t.tab_browsing_area	= _$("tab_browsing_area");
		t.test_font_size	= _$("test_font_size");
		a = t.textarea;
		
		if(!s['is_editable'])
			t.set_editable(false);
		
		t.set_show_line_colors( s['show_line_colors'] );
		
		if(syntax_selec= _$("syntax_selection"))
		{
			// set up syntax selection lsit in the toolbar
			for(var i=0; i<t.syntax_list.length; i++) {
				var syntax= t.syntax_list[i];
				var option= document.createElement("option");
				option.value= syntax;
				if(syntax==s['syntax'])
					option.selected= "selected";
				option.innerHTML= t.get_translation("syntax_" + syntax, "word");
				syntax_selec.appendChild(option);
			}
		}
		
		// add plugins buttons in the toolbar
		spans= parent.getChildren(_$("toolbar_1"), "span", "", "", "all", -1);
		
		for(var i=0; i<spans.length; i++){
		
			id=spans[i].id.replace(/tmp_tool_(.*)/, "$1");
			if(id!= spans[i].id){
				for(var j in t.plugins){
					if(typeof(t.plugins[j].get_control_html)=="function" ){
						html=t.plugins[j].get_control_html(id);
						if(html!=false){
							html= t.get_translation(html, "template");
							var new_span= document.createElement("span");
							new_span.innerHTML= html;				
							var father= spans[i].parentNode;
							spans[i].parentNode.replaceChild(new_span, spans[i]);	
							break; // exit the for loop					
						}
					}
				}
			}
		}
		
		// init datas
		//a.value	= 'a';//editAreas[t.id]["textarea"].value;
	
		if(s["debug"])
		{
			t.debug=parent.document.getElementById("edit_area_debug_"+t.id);
		}
		// init size		
		//this.update_size();
		
		if(_$("redo") != null)
			t.switchClassSticky(_$("redo"), 'editAreaButtonDisabled', true);
		
		// insert css rules for highlight mode		
		if(typeof(parent.editAreaLoader.syntax[s["syntax"]])!="undefined"){
			for(var i in parent.editAreaLoader.syntax){
				if (typeof(parent.editAreaLoader.syntax[i]["styles"]) != "undefined"){
					t.add_style(parent.editAreaLoader.syntax[i]["styles"]);
				}
			}
		}
	
		// init key events
		if(t.isOpera)
			_$("editor").onkeypress	= keyDown;
		else
			_$("editor").onkeydown	= keyDown;

		for(var i=0; i<t.inlinePopup.length; i++){
			if(t.isOpera)
				_$(t.inlinePopup[i]["popup_id"]).onkeypress	= keyDown;
			else
				_$(t.inlinePopup[i]["popup_id"]).onkeydown	= keyDown;
		}
		
		if(s["allow_resize"]=="both" || s["allow_resize"]=="x" || s["allow_resize"]=="y")
			t.allow_resize(true);
		
		parent.editAreaLoader.toggle(t.id, "on");
		//a.focus();
		// line selection init
		t.change_smooth_selection_mode(editArea.smooth_selection);
		// highlight
		t.execCommand("change_highlight", s["start_highlight"]);
	
		// get font size datas		
		t.set_font(editArea.settings["font_family"], editArea.settings["font_size"]);
		
		// set unselectable text
		children= parent.getChildren(document.body, "", "selec", "none", "all", -1);
		for(var i=0; i<children.length; i++){
			if(t.isIE)
				children[i].unselectable = true; // IE
			else
				children[i].onmousedown= function(){return false};
		/*	children[i].style.MozUserSelect = "none"; // Moz
			children[i].style.KhtmlUserSelect = "none";  // Konqueror/Safari*/
		}
		
		a.spellcheck= s["gecko_spellcheck"];
	
		/** Browser specific style fixes **/
		
		// fix rendering bug for highlighted lines beginning with no tabs
		if( t.isFirefox >= '3' ) {
			t.content_highlight.style.paddingLeft= "1px";
			t.selection_field.style.paddingLeft= "1px";
			t.selection_field_text.style.paddingLeft= "1px";
		}
		
		if(t.isIE && t.isIE < 8 ){
			a.style.marginTop= "-1px";
		}
		/*
		if(t.isOpera){
			t.editor_area.style.position= "absolute";
		}*/
		
		if( t.isSafari ){
			t.editor_area.style.position	= "absolute";
			a.style.marginLeft		="-3px";
			if( t.isSafari < 3.2 ) // Safari 3.0 (3.1?)
				a.style.marginTop	="1px";
		}
		
		// si le textarea n'est pas grand, un click sous le textarea doit provoquer un focus sur le textarea
		parent.editAreaLoader.add_event(t.result, "click", function(e){ if((e.target || e.srcElement)==editArea.result) { editArea.area_select(editArea.textarea.value.length, 0);}  });
		
		if(s['is_multi_files']!=false)
			t.open_file({'id': t.curr_file, 'text': ''});
	
		t.set_word_wrap( s['word_wrap'] );
		
		setTimeout("editArea.focus();editArea.manage_size();editArea.execCommand('EA_load');", 10);		
		//start checkup routine
		t.check_undo();
		t.check_line_selection(true);
		t.scroll_to_view();
		
		for(var i in t.plugins){
			if(typeof(t.plugins[i].onload)=="function")
				t.plugins[i].onload();
		}
		if(s['fullscreen']==true)
			t.toggle_full_screen(true);
	
		parent.editAreaLoader.add_event(window, "resize", editArea.update_size);
		parent.editAreaLoader.add_event(parent.window, "resize", editArea.update_size);
		parent.editAreaLoader.add_event(top.window, "resize", editArea.update_size);
		parent.editAreaLoader.add_event(window, "unload", function(){
			// in case where editAreaLoader have been already cleaned
			if( parent.editAreaLoader )
			{
				parent.editAreaLoader.remove_event(parent.window, "resize", editArea.update_size);
		  		parent.editAreaLoader.remove_event(top.window, "resize", editArea.update_size);
			}
			if(editAreas[editArea.id] && editAreas[editArea.id]["displayed"]){
				editArea.execCommand("EA_unload");
			}
		});
		
		
		/*date= new Date();
		alert(date.getTime()- parent.editAreaLoader.start_time);*/
	};
	
	
	
	//called by the toggle_on
	EditArea.prototype.update_size= function(){
		var d=document,pd=parent.document,height,width,popup,maxLeft,maxTop;
		
		if( typeof editAreas != 'undefined' && editAreas[editArea.id] && editAreas[editArea.id]["displayed"]==true){
			if(editArea.fullscreen['isFull']){	
				pd.getElementById("frame_"+editArea.id).style.width		= pd.getElementsByTagName("html")[0].clientWidth + "px";
				pd.getElementById("frame_"+editArea.id).style.height	= pd.getElementsByTagName("html")[0].clientHeight + "px";
			}
			
			if(editArea.tab_browsing_area.style.display=='block' && ( !editArea.isIE || editArea.isIE >= 8 ) )
			{
				editArea.tab_browsing_area.style.height	= "0px";
				editArea.tab_browsing_area.style.height	= (editArea.result.offsetTop - editArea.tab_browsing_area.offsetTop -1)+"px";
			}
			
			height	= d.body.offsetHeight - editArea.get_all_toolbar_height() - 4;
			editArea.result.style.height	= height +"px";
			
			width	= d.body.offsetWidth -2;
			editArea.result.style.width		= width+"px";
			//alert("result h: "+ height+" w: "+width+"\ntoolbar h: "+this.get_all_toolbar_height()+"\nbody_h: "+document.body.offsetHeight);
			
			// check that the popups don't get out of the screen
			for( i=0; i < editArea.inlinePopup.length; i++ )
			{
				popup	= _$(editArea.inlinePopup[i]["popup_id"]);
				maxLeft	= d.body.offsetWidth - popup.offsetWidth;
				maxTop	= d.body.offsetHeight - popup.offsetHeight;
				if( popup.offsetTop > maxTop )
					popup.style.top		= maxTop+"px";
				if( popup.offsetLeft > maxLeft )
					popup.style.left	= maxLeft+"px";
			}
			
			editArea.manage_size( true );
			editArea.fixLinesHeight( editArea.textarea.value, 0,-1);
		}		
	};
	
	
	EditArea.prototype.manage_size= function(onlyOneTime){
		if(!editAreas[this.id])
			return false;
			
		if(editAreas[this.id]["displayed"]==true && this.textareaFocused)
		{
			var area_height,resized= false;
			
			//1) Manage display width
			//1.1) Calc the new width to use for display
			if( !this.settings['word_wrap'] )
			{
				var area_width= this.textarea.scrollWidth;
				area_height= this.textarea.scrollHeight;
				// bug on old opera versions
				if(this.isOpera && this.isOpera < 9.6 ){
					area_width=10000; 								
				}
				//1.2) the width is not the same, we must resize elements
				if(this.textarea.previous_scrollWidth!=area_width)
				{	
					this.container.style.width= area_width+"px";
					this.textarea.style.width= area_width+"px";
					this.content_highlight.style.width= area_width+"px";	
					this.textarea.previous_scrollWidth=area_width;
					resized=true;
				}
			}
			// manage wrap width
			if( this.settings['word_wrap'] )
			{
				newW=this.textarea.offsetWidth;
				if( this.isFirefox || this.isIE )
					newW-=2;
				if( this.isSafari )
					newW-=6;
				this.content_highlight.style.width=this.selection_field_text.style.width=this.selection_field.style.width=this.test_font_size.style.width=newW+"px";
			}
			
			//2) Manage display height
			//2.1) Calc the new height to use for display
			if( this.isOpera || this.isFirefox || this.isSafari ) { 
				area_height= this.getLinePosTop( this.last_selection["nb_line"] + 1 );
			} else {
				area_height = this.textarea.scrollHeight;
			}	
			//2.2) the width is not the same, we must resize elements 
			if(this.textarea.previous_scrollHeight!=area_height)	
			{	
				this.container.style.height= (area_height+2)+"px";
				this.textarea.style.height= area_height+"px";
				this.content_highlight.style.height= area_height+"px";	
				this.textarea.previous_scrollHeight= area_height;
				resized=true;
			}
		
			//3) if there is new lines, we add new line numbers in the line numeration area
			if(this.last_selection["nb_line"] >= this.line_number)
			{
				var newLines= '', destDiv=_$("line_number"), start=this.line_number, end=this.last_selection["nb_line"]+100;
				for( i = start+1; i < end; i++ )
				{
					newLines+='<div id="line_'+ i +'">'+i+"</div>";
					this.line_number++;
				}
				destDiv.innerHTML= destDiv.innerHTML + newLines;
				
				this.fixLinesHeight( this.textarea.value, start, -1 );
			}
		
			//4) be sure the text is well displayed
			this.textarea.scrollTop="0px";
			this.textarea.scrollLeft="0px";
			if(resized==true){
				this.scroll_to_view();
			}
		}
		
		if(!onlyOneTime)
			setTimeout("editArea.manage_size();", 100);
	};
	
	EditArea.prototype.execCommand= function(cmd, param){
		
		for(var i in this.plugins){
			if(typeof(this.plugins[i].execCommand)=="function"){
				if(!this.plugins[i].execCommand(cmd, param))
					return;
			}
		}
		switch(cmd){
			case "save":
				if(this.settings["save_callback"].length>0)
					eval("parent."+this.settings["save_callback"]+"('"+ this.id +"', editArea.textarea.value);");
				break;
			case "load":
				if(this.settings["load_callback"].length>0)
					eval("parent."+this.settings["load_callback"]+"('"+ this.id +"');");
				break;
			case "onchange":
				if(this.settings["change_callback"].length>0)
					eval("parent."+this.settings["change_callback"]+"('"+ this.id +"');");
				break;		
			case "EA_load":
				if(this.settings["EA_load_callback"].length>0)
					eval("parent."+this.settings["EA_load_callback"]+"('"+ this.id +"');");
				break;
			case "EA_unload":
				if(this.settings["EA_unload_callback"].length>0)
					eval("parent."+this.settings["EA_unload_callback"]+"('"+ this.id +"');");
				break;
			case "toggle_on":
				if(this.settings["EA_toggle_on_callback"].length>0)
					eval("parent."+this.settings["EA_toggle_on_callback"]+"('"+ this.id +"');");
				break;
			case "toggle_off":
				if(this.settings["EA_toggle_off_callback"].length>0)
					eval("parent."+this.settings["EA_toggle_off_callback"]+"('"+ this.id +"');");
				break;
			case "re_sync":
				if(!this.do_highlight)
					break;
			case "file_switch_on":
				if(this.settings["EA_file_switch_on_callback"].length>0)
					eval("parent."+this.settings["EA_file_switch_on_callback"]+"(param);");
				break;
			case "file_switch_off":
				if(this.settings["EA_file_switch_off_callback"].length>0)
					eval("parent."+this.settings["EA_file_switch_off_callback"]+"(param);");
				break;
			case "file_close":
				if(this.settings["EA_file_close_callback"].length>0)
					return eval("parent."+this.settings["EA_file_close_callback"]+"(param);");
				break;
			
			default:
				if(typeof(eval("editArea."+cmd))=="function")
				{
					if(this.settings["debug"])
						eval("editArea."+ cmd +"(param);");
					else
						try{eval("editArea."+ cmd +"(param);");}catch(e){};
				}
		}
	};
	
	EditArea.prototype.get_translation= function(word, mode){
		if(mode=="template")
			return parent.editAreaLoader.translate(word, this.settings["language"], mode);
		else
			return parent.editAreaLoader.get_word_translation(word, this.settings["language"]);
	};
	
	EditArea.prototype.add_plugin= function(plug_name, plug_obj){
		for(var i=0; i<this.settings["plugins"].length; i++){
			if(this.settings["plugins"][i]==plug_name){
				this.plugins[plug_name]=plug_obj;
				plug_obj.baseURL=parent.editAreaLoader.baseURL + "plugins/" + plug_name + "/";
				if( typeof(plug_obj.init)=="function" )
					plug_obj.init();
			}
		}
	};
	
	EditArea.prototype.load_css= function(url){
		try{
			link = document.createElement("link");
			link.type = "text/css";
			link.rel= "stylesheet";
			link.media="all";
			link.href = url;
			head = document.getElementsByTagName("head");
			head[0].appendChild(link);
		}catch(e){
			document.write("<link href='"+ url +"' rel='stylesheet' type='text/css' />");
		}
	};
	
	EditArea.prototype.load_script= function(url){
		try{
			script = document.createElement("script");
			script.type = "text/javascript";
			script.src  = url;
			script.charset= "UTF-8";
			head = document.getElementsByTagName("head");
			head[0].appendChild(script);
		}catch(e){
			document.write("<script type='text/javascript' src='" + url + "' charset=\"UTF-8\"><"+"/script>");
		}
	};
	
	// add plugin translation to language translation array
	EditArea.prototype.add_lang= function(language, values){
		if(!parent.editAreaLoader.lang[language])
			parent.editAreaLoader.lang[language]={};
		for(var i in values)
			parent.editAreaLoader.lang[language][i]= values[i];
	};
	
	// short cut for document.getElementById()
	function _$(id){return document.getElementById( id );};

	var editArea = new EditArea();	
	parent.editAreaLoader.add_event(window, "load", init);
	
	function init(){		
		setTimeout("editArea.init();  ", 10);
	};
