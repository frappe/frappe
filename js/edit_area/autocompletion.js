/**
 * Autocompletion class
 * 
 * An auto completion box appear while you're writing. It's possible to force it to appear with Ctrl+Space short cut
 * 
 * Loaded as a plugin inside editArea (everything made here could have been made in the plugin directory)
 * But is definitly linked to syntax selection (no need to do 2 different files for color and auto complete for each syntax language)
 * and add a too important feature that many people would miss if included as a plugin
 * 
 * - init param: autocompletion_start
 * - Button name: "autocompletion"
 */  

var EditArea_autocompletion= {
	
	/**
	 * Get called once this file is loaded (editArea still not initialized)
	 *
	 * @return nothing	 
	 */	 	 	
	init: function(){	
		//	alert("test init: "+ this._someInternalFunction(2, 3));
		
		if(editArea.settings["autocompletion"])
			this.enabled= true;
		else
			this.enabled= false;
		this.current_word		= false;
		this.shown				= false;
		this.selectIndex		= -1;
		this.forceDisplay		= false;
		this.isInMiddleWord		= false;
		this.autoSelectIfOneResult	= false;
		this.delayBeforeDisplay	= 100;
		this.checkDelayTimer	= false;
		this.curr_syntax_str	= '';
		
		this.file_syntax_datas	= {};
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
	/*,get_control_html: function(ctrl_name){
		switch( ctrl_name ){
			case 'autocompletion':
				// Control id, button img, command
				return parent.editAreaLoader.get_button_html('autocompletion_but', 'autocompletion.gif', 'toggle_autocompletion', false, this.baseURL);
				break;
		}
		return false;
	}*/
	/**
	 * Get called once EditArea is fully loaded and initialised
	 *	 
	 * @return nothing
	 */	 	 	
	,onload: function(){ 
		if(this.enabled)
		{
			var icon= document.getElementById("autocompletion");
			if(icon)
				editArea.switchClassSticky(icon, 'editAreaButtonSelected', true);
		}
		
		this.container	= document.createElement('div');
		this.container.id	= "auto_completion_area";
		editArea.container.insertBefore( this.container, editArea.container.firstChild );
		
		// add event detection for hiding suggestion box
		parent.editAreaLoader.add_event( document, "click", function(){ editArea.plugins['autocompletion']._hide();} );
		parent.editAreaLoader.add_event( editArea.textarea, "blur", function(){ editArea.plugins['autocompletion']._hide();} );
		
	}
	
	/**
	 * Is called each time the user touch a keyboard key.
	 *	 
	 * @param (event) e: the keydown event
	 * @return true - pass to next handler in chain, false - stop chain execution
	 * @type boolean	 
	 */
	,onkeydown: function(e){
		if(!this.enabled)
			return true;
			
		if (EA_keys[e.keyCode])
			letter=EA_keys[e.keyCode];
		else
			letter=String.fromCharCode(e.keyCode);	
		// shown
		if( this._isShown() )
		{	
			// if escape, hide the box
			if(letter=="Esc")
			{
				this._hide();
				return false;
			}
			// Enter
			else if( letter=="Entrer")
			{
				var as	= this.container.getElementsByTagName('A');
				// select a suggested entry
				if( this.selectIndex >= 0 && this.selectIndex < as.length )
				{
					as[ this.selectIndex ].onmousedown();
					return false
				}
				// simply add an enter in the code
				else
				{
					this._hide();
					return true;
				}
			}
			else if( letter=="Tab" || letter=="Down")
			{
				this._selectNext();
				return false;
			}
			else if( letter=="Up")
			{
				this._selectBefore();
				return false;
			}
		}
		// hidden
		else
		{
			
		}
		
		// show current suggestion list and do autoSelect if possible (no matter it's shown or hidden)
		if( letter=="Space" && CtrlPressed(e) )
		{
			//parent.console.log('SHOW SUGGEST');
			this.forceDisplay 			= true;
			this.autoSelectIfOneResult	= true;
			this._checkLetter();
			return false;
		}
		
		// wait a short period for check that the cursor isn't moving
		setTimeout("editArea.plugins['autocompletion']._checkDelayAndCursorBeforeDisplay();", editArea.check_line_selection_timer +5 );
		this.checkDelayTimer = false;
		return true;
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
		switch( cmd ){
			case 'toggle_autocompletion':
				var icon= document.getElementById("autocompletion");
				if(!this.enabled)
				{
					if(icon != null){
						editArea.restoreClass(icon);
						editArea.switchClassSticky(icon, 'editAreaButtonSelected', true);
					}
					this.enabled= true;
				}
				else
				{
					this.enabled= false;
					if(icon != null)
						editArea.switchClassSticky(icon, 'editAreaButtonNormal', false);
				}
				return true;
		}
		return true;
	}
	,_checkDelayAndCursorBeforeDisplay: function()
	{
		this.checkDelayTimer = setTimeout("if(editArea.textarea.selectionStart == "+ editArea.textarea.selectionStart +") EditArea_autocompletion._checkLetter();",  this.delayBeforeDisplay - editArea.check_line_selection_timer - 5 );
	}
	// hide the suggested box
	,_hide: function(){
		this.container.style.display="none";
		this.selectIndex	= -1;
		this.shown	= false;
		this.forceDisplay	= false;
		this.autoSelectIfOneResult = false;
	}
	// display the suggested box
	,_show: function(){
		if( !this._isShown() )
		{
			this.container.style.display="block";
			this.selectIndex	= -1;
			this.shown	= true;
		}
	}
	// is the suggested box displayed?
	,_isShown: function(){
		return this.shown;
	}
	// setter and getter
	,_isInMiddleWord: function( new_value ){
		if( typeof( new_value ) == "undefined" )
			return this.isInMiddleWord;
		else
			this.isInMiddleWord	= new_value;
	}
	// select the next element in the suggested box
	,_selectNext: function()
	{
		var as	= this.container.getElementsByTagName('A');
		
		// clean existing elements
		for( var i=0; i<as.length; i++ )
		{
			if( as[i].className )
				as[i].className	= as[i].className.replace(/ focus/g, '');
		}
		
		this.selectIndex++;	
		this.selectIndex	= ( this.selectIndex >= as.length || this.selectIndex < 0 ) ? 0 : this.selectIndex;
		as[ this.selectIndex ].className	+= " focus";
	}
	// select the previous element in the suggested box
	,_selectBefore: function()
	{
		var as	= this.container.getElementsByTagName('A');
		
		// clean existing elements
		for( var i=0; i<as.length; i++ )
		{
			if( as[i].className )
				as[i].className	= as[ i ].className.replace(/ focus/g, '');
		}
		
		this.selectIndex--;
		
		this.selectIndex	= ( this.selectIndex >= as.length || this.selectIndex < 0 ) ? as.length-1 : this.selectIndex;
		as[ this.selectIndex ].className	+= " focus";
	}
	,_select: function( content )
	{
		cursor_forced_position	= content.indexOf( '{@}' );
		content	= content.replace(/{@}/g, '' );
		editArea.getIESelection();
		
		// retrive the number of matching characters
		var start_index	= Math.max( 0, editArea.textarea.selectionEnd - content.length );
		
		line_string	= 	editArea.textarea.value.substring( start_index, editArea.textarea.selectionEnd + 1);
		limit	= line_string.length -1;
		nbMatch	= 0;
		for( i =0; i<limit ; i++ )
		{
			if( line_string.substring( limit - i - 1, limit ) == content.substring( 0, i + 1 ) )
				nbMatch = i + 1;
		}
		// if characters match, we should include them in the selection that will be replaced
		if( nbMatch > 0 )
			parent.editAreaLoader.setSelectionRange(editArea.id, editArea.textarea.selectionStart - nbMatch , editArea.textarea.selectionEnd);
		
		parent.editAreaLoader.setSelectedText(editArea.id, content );
		range= parent.editAreaLoader.getSelectionRange(editArea.id);
		
		if( cursor_forced_position != -1 )
			new_pos	= range["end"] - ( content.length-cursor_forced_position );
		else
			new_pos	= range["end"];	
		parent.editAreaLoader.setSelectionRange(editArea.id, new_pos, new_pos);
		this._hide();
	}
	
	
	/**
	 * Parse the AUTO_COMPLETION part of syntax definition files
	 */
	,_parseSyntaxAutoCompletionDatas: function(){
		//foreach syntax loaded
		for(var lang in parent.editAreaLoader.load_syntax)
		{
			if(!parent.editAreaLoader.syntax[lang]['autocompletion'])	// init the regexp if not already initialized
			{
				parent.editAreaLoader.syntax[lang]['autocompletion']= {};
				// the file has auto completion datas
				if(parent.editAreaLoader.load_syntax[lang]['AUTO_COMPLETION'])
				{
					// parse them
					for(var i in parent.editAreaLoader.load_syntax[lang]['AUTO_COMPLETION'])
					{
						datas	= parent.editAreaLoader.load_syntax[lang]['AUTO_COMPLETION'][i];
						tmp	= {};
						if(datas["CASE_SENSITIVE"]!="undefined" && datas["CASE_SENSITIVE"]==false)
							tmp["modifiers"]="i";
						else
							tmp["modifiers"]="";
						tmp["prefix_separator"]= datas["REGEXP"]["prefix_separator"];
						tmp["match_prefix_separator"]= new RegExp( datas["REGEXP"]["prefix_separator"] +"$", tmp["modifiers"]);
						tmp["match_word"]= new RegExp("(?:"+ datas["REGEXP"]["before_word"] +")("+ datas["REGEXP"]["possible_words_letters"] +")$", tmp["modifiers"]);
						tmp["match_next_letter"]= new RegExp("^("+ datas["REGEXP"]["letter_after_word_must_match"] +")$", tmp["modifiers"]);
						tmp["keywords"]= {};
						//console.log( datas["KEYWORDS"] );
						for( var prefix in datas["KEYWORDS"] )
						{
							tmp["keywords"][prefix]= {
								prefix: prefix,
								prefix_name: prefix,
								prefix_reg: new RegExp("(?:"+ parent.editAreaLoader.get_escaped_regexp( prefix ) +")(?:"+ tmp["prefix_separator"] +")$", tmp["modifiers"] ),
								datas: []
							};
							for( var j=0; j<datas["KEYWORDS"][prefix].length; j++ )
							{
								tmp["keywords"][prefix]['datas'][j]= {
									is_typing: datas["KEYWORDS"][prefix][j][0],
									// if replace with is empty, replace with the is_typing value
									replace_with: datas["KEYWORDS"][prefix][j][1] ? datas["KEYWORDS"][prefix][j][1].replace('§', datas["KEYWORDS"][prefix][j][0] ) : '',
									comment: datas["KEYWORDS"][prefix][j][2] ? datas["KEYWORDS"][prefix][j][2] : '' 
								};
								
								// the replace with shouldn't be empty
								if( tmp["keywords"][prefix]['datas'][j]['replace_with'].length == 0 )
									tmp["keywords"][prefix]['datas'][j]['replace_with'] = tmp["keywords"][prefix]['datas'][j]['is_typing'];
								
								// if the comment is empty, display the replace_with value
								if( tmp["keywords"][prefix]['datas'][j]['comment'].length == 0 )
									 tmp["keywords"][prefix]['datas'][j]['comment'] = tmp["keywords"][prefix]['datas'][j]['replace_with'].replace(/{@}/g, '' );
							}
								
						}
						tmp["max_text_length"]= datas["MAX_TEXT_LENGTH"];
						parent.editAreaLoader.syntax[lang]['autocompletion'][i]	= tmp;
					}
				}
			}
		}
	}
	
	,_checkLetter: function(){
		// check that syntax hasn't changed
		if( this.curr_syntax_str != editArea.settings['syntax'] )
		{
			if( !parent.editAreaLoader.syntax[editArea.settings['syntax']]['autocompletion'] )
				this._parseSyntaxAutoCompletionDatas();
			this.curr_syntax= parent.editAreaLoader.syntax[editArea.settings['syntax']]['autocompletion'];
			this.curr_syntax_str = editArea.settings['syntax'];
			//console.log( this.curr_syntax );
		}
		
		if( editArea.is_editable )
		{
			time=new Date;
			t1= time.getTime();
			editArea.getIESelection();
			this.selectIndex	= -1;
			start=editArea.textarea.selectionStart;
			var str	= editArea.textarea.value;
			var results= [];
			
			
			for(var i in this.curr_syntax)
			{
				var last_chars	= str.substring(Math.max(0, start-this.curr_syntax[i]["max_text_length"]), start);
				var matchNextletter	= str.substring(start, start+1).match( this.curr_syntax[i]["match_next_letter"]);
				// if not writting in the middle of a word or if forcing display
				if( matchNextletter || this.forceDisplay )
				{
					// check if the last chars match a separator
					var match_prefix_separator = last_chars.match(this.curr_syntax[i]["match_prefix_separator"]);
			
					// check if it match a possible word
					var match_word= last_chars.match(this.curr_syntax[i]["match_word"]);
					
					//console.log( match_word );
					if( match_word )
					{
						var begin_word= match_word[1];
						var match_curr_word= new RegExp("^"+ parent.editAreaLoader.get_escaped_regexp( begin_word ), this.curr_syntax[i]["modifiers"]);
						//console.log( match_curr_word );
						for(var prefix in this.curr_syntax[i]["keywords"])
						{
						//	parent.console.log( this.curr_syntax[i]["keywords"][prefix] );
							for(var j=0; j<this.curr_syntax[i]["keywords"][prefix]['datas'].length; j++)
							{
						//		parent.console.log( this.curr_syntax[i]["keywords"][prefix]['datas'][j]['is_typing'] );
								// the key word match or force display 
								if( this.curr_syntax[i]["keywords"][prefix]['datas'][j]['is_typing'].match(match_curr_word) )
								{
							//		parent.console.log('match');
									hasMatch = false;
									var before = last_chars.substr( 0, last_chars.length - begin_word.length );
									
									// no prefix to match => it's valid
									if( !match_prefix_separator && this.curr_syntax[i]["keywords"][prefix]['prefix'].length == 0 )
									{
										if( ! before.match( this.curr_syntax[i]["keywords"][prefix]['prefix_reg'] ) )
											hasMatch = true;
									}
									// we still need to check the prefix if there is one
									else if( this.curr_syntax[i]["keywords"][prefix]['prefix'].length > 0 )
									{
										if( before.match( this.curr_syntax[i]["keywords"][prefix]['prefix_reg'] ) )
											hasMatch = true;
									}
									
									if( hasMatch )
										results[results.length]= [ this.curr_syntax[i]["keywords"][prefix], this.curr_syntax[i]["keywords"][prefix]['datas'][j] ];
								}	
							}
						}
					}
					// it doesn't match any possible word but we want to display something
					// we'll display to list of all available words
					else if( this.forceDisplay || match_prefix_separator )
					{
						for(var prefix in this.curr_syntax[i]["keywords"])
						{
							for(var j=0; j<this.curr_syntax[i]["keywords"][prefix]['datas'].length; j++)
							{
								hasMatch = false;
								// no prefix to match => it's valid
								if( !match_prefix_separator && this.curr_syntax[i]["keywords"][prefix]['prefix'].length == 0 )
								{
									hasMatch	= true;
								}
								// we still need to check the prefix if there is one
								else if( match_prefix_separator && this.curr_syntax[i]["keywords"][prefix]['prefix'].length > 0 )
								{
									var before = last_chars; //.substr( 0, last_chars.length );
									if( before.match( this.curr_syntax[i]["keywords"][prefix]['prefix_reg'] ) )
										hasMatch = true;
								}	
									
								if( hasMatch )
									results[results.length]= [ this.curr_syntax[i]["keywords"][prefix], this.curr_syntax[i]["keywords"][prefix]['datas'][j] ];	
							}
						}
					}
				}
			}
			
			// there is only one result, and we can select it automatically
			if( results.length == 1 && this.autoSelectIfOneResult )
			{
			//	console.log( results );
				this._select( results[0][1]['replace_with'] );
			}
			else if( results.length == 0 )
			{
				this._hide();
			}
			else
			{
				// build the suggestion box content
				var lines=[];
				for(var i=0; i<results.length; i++)
				{
					var line= "<li><a href=\"#\" class=\"entry\" onmousedown=\"EditArea_autocompletion._select('"+ results[i][1]['replace_with'].replace(new RegExp('"', "g"), "&quot;") +"');return false;\">"+ results[i][1]['comment'];
					if(results[i][0]['prefix_name'].length>0)
						line+='<span class="prefix">'+ results[i][0]['prefix_name'] +'</span>';
					line+='</a></li>';
					lines[lines.length]=line;
				}
				// sort results
				this.container.innerHTML		= '<ul>'+ lines.sort().join('') +'</ul>';
				
				var cursor	= _$("cursor_pos");
				this.container.style.top		= ( cursor.cursor_top + editArea.lineHeight ) +"px";
				this.container.style.left		= ( cursor.cursor_left + 8 ) +"px";
				this._show();
			}
				
			this.autoSelectIfOneResult = false;
			time=new Date;
			t2= time.getTime();
		
			//parent.console.log( begin_word +"\n"+ (t2-t1) +"\n"+ html );
		}
	}
};

// Load as a plugin
editArea.settings['plugins'][ editArea.settings['plugins'].length ] = 'autocompletion';
editArea.add_plugin('autocompletion', EditArea_autocompletion);