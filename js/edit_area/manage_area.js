	EditArea.prototype.focus = function() {
		this.textarea.focus();
		this.textareaFocused=true;
	};


	EditArea.prototype.check_line_selection= function(timer_checkup){
		var changes, infos, new_top, new_width,i;
		
		var t1=t2=t2_1=t3=tLines=tend= new Date().getTime();
		// l'editeur n'existe plus => on quitte
		if(!editAreas[this.id])
			return false;
		
		if(!this.smooth_selection && !this.do_highlight)
		{
			//do nothing
		}
		else if(this.textareaFocused && editAreas[this.id]["displayed"]==true && this.isResizing==false)
		{
			infos	= this.get_selection_infos();
			changes	= this.checkTextEvolution( typeof( this.last_selection['full_text'] ) == 'undefined' ? '' : this.last_selection['full_text'], infos['full_text'] );
		
			t2= new Date().getTime();
			
			// if selection change
			if(this.last_selection["line_start"] != infos["line_start"] || this.last_selection["line_nb"] != infos["line_nb"] || infos["full_text"] != this.last_selection["full_text"] || this.reload_highlight || this.last_selection["selectionStart"] != infos["selectionStart"] || this.last_selection["selectionEnd"] != infos["selectionEnd"] || !timer_checkup )
			{
				// move and adjust text selection elements
				new_top		= this.getLinePosTop( infos["line_start"] );
				new_width	= Math.max(this.textarea.scrollWidth, this.container.clientWidth -50);
				this.selection_field.style.top=this.selection_field_text.style.top=new_top+"px";
				if(!this.settings['word_wrap']){	
					this.selection_field.style.width=this.selection_field_text.style.width=this.test_font_size.style.width=new_width+"px";
				}
				
				// usefull? => _$("cursor_pos").style.top=new_top+"px";	
		
				if(this.do_highlight==true)
				{
					// fill selection elements
					var curr_text	= infos["full_text"].split("\n");
					var content		= "";
					//alert("length: "+curr_text.length+ " i: "+ Math.max(0,infos["line_start"]-1)+ " end: "+Math.min(curr_text.length, infos["line_start"]+infos["line_nb"]-1)+ " line: "+infos["line_start"]+" [0]: "+curr_text[0]+" [1]: "+curr_text[1]);
					var start		= Math.max(0,infos["line_start"]-1);
					var end			= Math.min(curr_text.length, infos["line_start"]+infos["line_nb"]-1);
					
					//curr_text[start]= curr_text[start].substr(0,infos["curr_pos"]-1) +"¤_overline_¤"+ curr_text[start].substr(infos["curr_pos"]-1);
					for(i=start; i< end; i++){
						content+= curr_text[i]+"\n";	
					}
					
					// add special chars arround selected characters
					selLength	= infos['selectionEnd'] - infos['selectionStart'];
					content		= content.substr( 0, infos["curr_pos"] - 1 ) + "\r\r" + content.substr( infos["curr_pos"] - 1, selLength ) + "\r\r" + content.substr( infos["curr_pos"] - 1 + selLength );
					content		= '<span>'+ content.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace("\r\r", '</span><strong>').replace("\r\r", '</strong><span>') +'</span>';
					
					if( this.isIE || ( this.isOpera && this.isOpera < 9.6 ) ) {
						this.selection_field.innerHTML= "<pre>" + content.replace(/^\r?\n/, "<br>") + "</pre>";
					} else {
						this.selection_field.innerHTML= content;
					}
					this.selection_field_text.innerHTML = this.selection_field.innerHTML;
					t2_1 = new Date().getTime();
					// check if we need to update the highlighted background 
					if(this.reload_highlight || (infos["full_text"] != this.last_text_to_highlight && (this.last_selection["line_start"]!=infos["line_start"] || this.show_line_colors || this.settings['word_wrap'] || this.last_selection["line_nb"]!=infos["line_nb"] || this.last_selection["nb_line"]!=infos["nb_line"]) ) )
					{
						this.maj_highlight(infos);
					}
				}		
			}
			t3= new Date().getTime();
			
			// manage line heights
			if( this.settings['word_wrap'] && infos["full_text"] != this.last_selection["full_text"])
			{
				// refresh only 1 line if text change concern only one line and that the total line number has not changed
				if( changes.newText.split("\n").length == 1 && this.last_selection['nb_line'] && infos['nb_line'] == this.last_selection['nb_line'] )
				{
					this.fixLinesHeight( infos['full_text'], changes.lineStart, changes.lineStart );
				}
				else
				{
					this.fixLinesHeight( infos['full_text'], changes.lineStart, -1 );
				}
			}
		
			tLines= new Date().getTime();
			// manage bracket finding
			if( infos["line_start"] != this.last_selection["line_start"] || infos["curr_pos"] != this.last_selection["curr_pos"] || infos["full_text"].length!=this.last_selection["full_text"].length || this.reload_highlight || !timer_checkup )
			{
				// move _cursor_pos
				var selec_char= infos["curr_line"].charAt(infos["curr_pos"]-1);
				var no_real_move=true;
				if(infos["line_nb"]==1 && (this.assocBracket[selec_char] || this.revertAssocBracket[selec_char]) ){
					
					no_real_move=false;					
					//findEndBracket(infos["line_start"], infos["curr_pos"], selec_char);
					if(this.findEndBracket(infos, selec_char) === true){
						_$("end_bracket").style.visibility	="visible";
						_$("cursor_pos").style.visibility	="visible";
						_$("cursor_pos").innerHTML			= selec_char;
						_$("end_bracket").innerHTML			= (this.assocBracket[selec_char] || this.revertAssocBracket[selec_char]);
					}else{
						_$("end_bracket").style.visibility	="hidden";
						_$("cursor_pos").style.visibility	="hidden";
					}
				}else{
					_$("cursor_pos").style.visibility	="hidden";
					_$("end_bracket").style.visibility	="hidden";
				}
				//alert("move cursor");
				this.displayToCursorPosition("cursor_pos", infos["line_start"], infos["curr_pos"]-1, infos["curr_line"], no_real_move);
				if(infos["line_nb"]==1 && infos["line_start"]!=this.last_selection["line_start"])
					this.scroll_to_view();
			}
			this.last_selection=infos;
		}
		
		tend= new Date().getTime();
		//if( (tend-t1) > 7 )
		//	console.log( "tps total: "+ (tend-t1) + " tps get_infos: "+ (t2-t1)+ " tps selec: "+ (t2_1-t2)+ " tps highlight: "+ (t3-t2_1) +" tps lines: "+ (tLines-t3) +" tps cursor+lines: "+ (tend-tLines)+" \n" );
		
		
		if(timer_checkup){
			setTimeout("editArea.check_line_selection(true)", this.check_line_selection_timer);
		}
	};


	EditArea.prototype.get_selection_infos= function(){
		var sel={}, start, end, len, str;
	
		this.getIESelection();
		start	= this.textarea.selectionStart;
		end		= this.textarea.selectionEnd;		
		
		if( this.last_selection["selectionStart"] == start && this.last_selection["selectionEnd"] == end && this.last_selection["full_text"] == this.textarea.value )
		{	
			return this.last_selection;
		}
			
		if(this.tabulation!="\t" && this.textarea.value.indexOf("\t")!=-1) 
		{	// can append only after copy/paste 
			len		= this.textarea.value.length;
			this.textarea.value	= this.replace_tab(this.textarea.value);
			start	= end	= start+(this.textarea.value.length-len);
			this.area_select( start, 0 );
		}
		
		sel["selectionStart"]	= start;
		sel["selectionEnd"]		= end;		
		sel["full_text"]		= this.textarea.value;
		sel["line_start"]		= 1;
		sel["line_nb"]			= 1;
		sel["curr_pos"]			= 0;
		sel["curr_line"]		= "";
		sel["indexOfCursor"]	= 0;
		sel["selec_direction"]	= this.last_selection["selec_direction"];

		//return sel;	
		var splitTab= sel["full_text"].split("\n");
		var nbLine	= Math.max(0, splitTab.length);		
		var nbChar	= Math.max(0, sel["full_text"].length - (nbLine - 1));	// (remove \n caracters from the count)
		if( sel["full_text"].indexOf("\r") != -1 )
			nbChar	= nbChar - ( nbLine - 1 );		// (remove \r caracters from the count)
		sel["nb_line"]	= nbLine;		
		sel["nb_char"]	= nbChar;
	
		if(start>0){
			str					= sel["full_text"].substr(0,start);
			sel["curr_pos"]		= start - str.lastIndexOf("\n");
			sel["line_start"]	= Math.max(1, str.split("\n").length);
		}else{
			sel["curr_pos"]=1;
		}
		if(end>start){
			sel["line_nb"]=sel["full_text"].substring(start,end).split("\n").length;
		}
		sel["indexOfCursor"]=start;		
		sel["curr_line"]=splitTab[Math.max(0,sel["line_start"]-1)];
	
		// determine in which direction the selection grow
		if(sel["selectionStart"] == this.last_selection["selectionStart"]){
			if(sel["selectionEnd"]>this.last_selection["selectionEnd"])
				sel["selec_direction"]= "down";
			else if(sel["selectionEnd"] == this.last_selection["selectionStart"])
				sel["selec_direction"]= this.last_selection["selec_direction"];
		}else if(sel["selectionStart"] == this.last_selection["selectionEnd"] && sel["selectionEnd"]>this.last_selection["selectionEnd"]){
			sel["selec_direction"]= "down";
		}else{
			sel["selec_direction"]= "up";
		}
		
		_$("nbLine").innerHTML	= nbLine;		
		_$("nbChar").innerHTML	= nbChar;		
		_$("linePos").innerHTML	= sel["line_start"];
		_$("currPos").innerHTML	= sel["curr_pos"];

		return sel;		
	};
	
	// set IE position in Firefox mode (textarea.selectionStart and textarea.selectionEnd)
	EditArea.prototype.getIESelection= function(){
		var selectionStart, selectionEnd, range, stored_range;
		
		if( !this.isIE )
			return false;
			
		// make it work as nowrap mode (easier for range manipulation with lineHeight)
		if( this.settings['word_wrap'] )
			this.textarea.wrap='off';
			
		try{
			range			= document.selection.createRange();
			stored_range	= range.duplicate();
			stored_range.moveToElementText( this.textarea );
			stored_range.setEndPoint( 'EndToEnd', range );
			if( stored_range.parentElement() != this.textarea )
				throw "invalid focus";
				
			// the range don't take care of empty lines in the end of the selection
			var scrollTop	= this.result.scrollTop + document.body.scrollTop;
			var relative_top= range.offsetTop - parent.calculeOffsetTop(this.textarea) + scrollTop;
			var line_start	= Math.round((relative_top / this.lineHeight) +1);
			var line_nb		= Math.round( range.boundingHeight / this.lineHeight );
						
			selectionStart	= stored_range.text.length - range.text.length;		
			selectionStart	+= ( line_start - this.textarea.value.substr(0, selectionStart).split("\n").length)*2;		// count missing empty \r to the selection
			selectionStart	-= ( line_start - this.textarea.value.substr(0, selectionStart).split("\n").length ) * 2;
			
			selectionEnd	= selectionStart + range.text.length;		
			selectionEnd	+= (line_start + line_nb - 1 - this.textarea.value.substr(0, selectionEnd ).split("\n").length)*2;			
		
			this.textarea.selectionStart	= selectionStart;
			this.textarea.selectionEnd		= selectionEnd;
		}
		catch(e){}
		
		// restore wrap mode
		if( this.settings['word_wrap'] )
			this.textarea.wrap='soft';
	};
	
	// select the text for IE (and take care of \r caracters)
	EditArea.prototype.setIESelection= function(){
		var a = this.textarea, nbLineStart, nbLineEnd, range;
		
		if( !this.isIE )
			return false;
		
		nbLineStart	= a.value.substr(0, a.selectionStart).split("\n").length - 1;
		nbLineEnd 	= a.value.substr(0, a.selectionEnd).split("\n").length - 1;
		range		= document.selection.createRange();
		range.moveToElementText( a );
		range.setEndPoint( 'EndToStart', range );
		
		range.moveStart('character', a.selectionStart - nbLineStart);
		range.moveEnd('character', a.selectionEnd - nbLineEnd - (a.selectionStart - nbLineStart)  );
		range.select();
	};
	
	
	
	EditArea.prototype.checkTextEvolution=function(lastText,newText){
		// ch will contain changes datas
		var ch={},baseStep=200, cpt=0, end, step,tStart=new Date().getTime();
	
		end		= Math.min(newText.length, lastText.length);
        step	= baseStep;
        // find how many chars are similar at the begin of the text						
		while( cpt<end && step>=1 ){
            if(lastText.substr(cpt, step) == newText.substr(cpt, step)){
                cpt+= step;
            }else{
                step= Math.floor(step/2);
            }
		}
		
		ch.posStart	= cpt;
		ch.lineStart= newText.substr(0, ch.posStart).split("\n").length -1;						
		
		cpt_last	= lastText.length;
        cpt			= newText.length;
        step		= baseStep;			
        // find how many chars are similar at the end of the text						
		while( cpt>=0 && cpt_last>=0 && step>=1 ){
            if(lastText.substr(cpt_last-step, step) == newText.substr(cpt-step, step)){
                cpt-= step;
                cpt_last-= step;
            }else{
                step= Math.floor(step/2);
            }
		}
		
		ch.posNewEnd	= cpt;
		ch.posLastEnd	= cpt_last;
		if(ch.posNewEnd<=ch.posStart){
			if(lastText.length < newText.length){
				ch.posNewEnd= ch.posStart + newText.length - lastText.length;
				ch.posLastEnd= ch.posStart;
			}else{
				ch.posLastEnd= ch.posStart + lastText.length - newText.length;
				ch.posNewEnd= ch.posStart;
			}
		} 
		ch.newText		= newText.substring(ch.posStart, ch.posNewEnd);
		ch.lastText		= lastText.substring(ch.posStart, ch.posLastEnd);			            
		
		ch.lineNewEnd	= newText.substr(0, ch.posNewEnd).split("\n").length -1;
		ch.lineLastEnd	= lastText.substr(0, ch.posLastEnd).split("\n").length -1;
		
		ch.newTextLine	= newText.split("\n").slice(ch.lineStart, ch.lineNewEnd+1).join("\n");
		ch.lastTextLine	= lastText.split("\n").slice(ch.lineStart, ch.lineLastEnd+1).join("\n");
		//console.log( ch );
		return ch;	
	};
	
	EditArea.prototype.tab_selection= function(){
		if(this.is_tabbing)
			return;
		this.is_tabbing=true;
		//infos=getSelectionInfos();
		//if( document.selection ){
		this.getIESelection();
		/* Insertion du code de formatage */
		var start = this.textarea.selectionStart;
		var end = this.textarea.selectionEnd;
		var insText = this.textarea.value.substring(start, end);
		
		/* Insert tabulation and ajust cursor position */
		var pos_start=start;
		var pos_end=end;
		if (insText.length == 0) {
			// if only one line selected
			this.textarea.value = this.textarea.value.substr(0, start) + this.tabulation + this.textarea.value.substr(end);
			pos_start = start + this.tabulation.length;
			pos_end=pos_start;
		} else {
			start= Math.max(0, this.textarea.value.substr(0, start).lastIndexOf("\n")+1);
			endText=this.textarea.value.substr(end);
			startText=this.textarea.value.substr(0, start);
			tmp= this.textarea.value.substring(start, end).split("\n");
			insText= this.tabulation+tmp.join("\n"+this.tabulation);
			this.textarea.value = startText + insText + endText;
			pos_start = start;
			pos_end= this.textarea.value.indexOf("\n", startText.length + insText.length);
			if(pos_end==-1)
				pos_end=this.textarea.value.length;
			//pos = start + repdeb.length + insText.length + ;
		}
		this.textarea.selectionStart = pos_start;
		this.textarea.selectionEnd = pos_end;
		
		//if( document.selection ){
		if(this.isIE)
		{
			this.setIESelection();
			setTimeout("editArea.is_tabbing=false;", 100);	// IE can't accept to make 2 tabulation without a little break between both
		}
		else
		{ 
			this.is_tabbing=false;
		}	
		
  	};
	
	EditArea.prototype.invert_tab_selection= function(){
		var t=this, a=this.textarea;
		if(t.is_tabbing)
			return;
		t.is_tabbing=true;
		//infos=getSelectionInfos();
		//if( document.selection ){
		t.getIESelection();
		
		var start	= a.selectionStart;
		var end		= a.selectionEnd;
		var insText	= a.value.substring(start, end);
		
		/* Tab remove and cursor seleciton adjust */
		var pos_start=start;
		var pos_end=end;
		if (insText.length == 0) {
			if(a.value.substring(start-t.tabulation.length, start)==t.tabulation)
			{
				a.value		= a.value.substr(0, start-t.tabulation.length) + a.value.substr(end);
				pos_start	= Math.max(0, start-t.tabulation.length);
				pos_end		= pos_start;
			}	
			/*
			a.value = a.value.substr(0, start) + t.tabulation + insText + a.value.substr(end);
			pos_start = start + t.tabulation.length;
			pos_end=pos_start;*/
		} else {
			start		= a.value.substr(0, start).lastIndexOf("\n")+1;
			endText		= a.value.substr(end);
			startText	= a.value.substr(0, start);
			tmp			= a.value.substring(start, end).split("\n");
			insText		= "";
			for(i=0; i<tmp.length; i++){				
				for(j=0; j<t.tab_nb_char; j++){
					if(tmp[i].charAt(0)=="\t"){
						tmp[i]=tmp[i].substr(1);
						j=t.tab_nb_char;
					}else if(tmp[i].charAt(0)==" ")
						tmp[i]=tmp[i].substr(1);
				}		
				insText+=tmp[i];
				if(i<tmp.length-1)
					insText+="\n";
			}
			//insText+="_";
			a.value		= startText + insText + endText;
			pos_start	= start;
			pos_end		= a.value.indexOf("\n", startText.length + insText.length);
			if(pos_end==-1)
				pos_end=a.value.length;
			//pos = start + repdeb.length + insText.length + ;
		}
		a.selectionStart = pos_start;
		a.selectionEnd = pos_end;
		
		//if( document.selection ){
		if(t.isIE){
			// select the text for IE
			t.setIESelection();
			setTimeout("editArea.is_tabbing=false;", 100);	// IE can accept to make 2 tabulation without a little break between both
		}else
			t.is_tabbing=false;
  	};
	
	EditArea.prototype.press_enter= function(){		
		if(!this.smooth_selection)
			return false;
		this.getIESelection();
		var scrollTop= this.result.scrollTop;
		var scrollLeft= this.result.scrollLeft;
		var start=this.textarea.selectionStart;
		var end= this.textarea.selectionEnd;
		var start_last_line= Math.max(0 , this.textarea.value.substring(0, start).lastIndexOf("\n") + 1 );
		var begin_line= this.textarea.value.substring(start_last_line, start).replace(/^([ \t]*).*/gm, "$1");
		var lineStart = this.textarea.value.substring(0, start).split("\n").length;
		if(begin_line=="\n" || begin_line=="\r" || begin_line.length==0)
		{
			return false;
		}
			
		if(this.isIE || ( this.isOpera && this.isOpera < 9.6 ) ){
			begin_line="\r\n"+ begin_line;
		}else{
			begin_line="\n"+ begin_line;
		}	
		//alert(start_last_line+" strat: "+start +"\n"+this.textarea.value.substring(start_last_line, start)+"\n_"+begin_line+"_")
		this.textarea.value= this.textarea.value.substring(0, start) + begin_line + this.textarea.value.substring(end);
		
		this.area_select(start+ begin_line.length ,0);
		// during this process IE scroll back to the top of the textarea
		if(this.isIE){
			this.result.scrollTop	= scrollTop;
			this.result.scrollLeft	= scrollLeft;
		}
		return true;
		
	};
	
	EditArea.prototype.findEndBracket= function(infos, bracket){
			
		var start=infos["indexOfCursor"];
		var normal_order=true;
		//curr_text=infos["full_text"].split("\n");
		if(this.assocBracket[bracket])
			endBracket=this.assocBracket[bracket];
		else if(this.revertAssocBracket[bracket]){
			endBracket=this.revertAssocBracket[bracket];
			normal_order=false;
		}	
		var end=-1;
		var nbBracketOpen=0;
		
		for(var i=start; i<infos["full_text"].length && i>=0; ){
			if(infos["full_text"].charAt(i)==endBracket){				
				nbBracketOpen--;
				if(nbBracketOpen<=0){
					//i=infos["full_text"].length;
					end=i;
					break;
				}
			}else if(infos["full_text"].charAt(i)==bracket)
				nbBracketOpen++;
			if(normal_order)
				i++;
			else
				i--;
		}
		
		//end=infos["full_text"].indexOf("}", start);
		if(end==-1)
			return false;	
		var endLastLine=infos["full_text"].substr(0, end).lastIndexOf("\n");			
		if(endLastLine==-1)
			line=1;
		else
			line= infos["full_text"].substr(0, endLastLine).split("\n").length + 1;
					
		var curPos= end - endLastLine - 1;
		var endLineLength	= infos["full_text"].substring(end).split("\n")[0].length;
		this.displayToCursorPosition("end_bracket", line, curPos, infos["full_text"].substring(endLastLine +1, end + endLineLength));
		return true;
	};
	
	EditArea.prototype.displayToCursorPosition= function(id, start_line, cur_pos, lineContent, no_real_move){
		var elem,dest,content,posLeft=0,posTop,fixPadding,topOffset,endElem;	

		elem		= this.test_font_size;
		dest		= _$(id);
		content		= "<span id='test_font_size_inner'>"+lineContent.substr(0, cur_pos).replace(/&/g,"&amp;").replace(/</g,"&lt;")+"</span><span id='endTestFont'>"+lineContent.substr(cur_pos).replace(/&/g,"&amp;").replace(/</g,"&lt;")+"</span>";
		if( this.isIE || ( this.isOpera && this.isOpera < 9.6 ) ) {
			elem.innerHTML= "<pre>" + content.replace(/^\r?\n/, "<br>") + "</pre>";
		} else {
			elem.innerHTML= content;
		}
		

		endElem		= _$('endTestFont');
		topOffset	= endElem.offsetTop;
		fixPadding	= parseInt( this.content_highlight.style.paddingLeft.replace("px", "") );
		posLeft 	= 45 + endElem.offsetLeft + ( !isNaN( fixPadding ) && topOffset > 0 ? fixPadding : 0 );
		posTop		= this.getLinePosTop( start_line ) + topOffset;// + Math.floor( ( endElem.offsetHeight - 1 ) / this.lineHeight ) * this.lineHeight;
	
		// detect the case where the span start on a line but has no display on it
		if( this.isIE && cur_pos > 0 && endElem.offsetLeft == 0 )
		{
			posTop	+=	this.lineHeight;
		}
		if(no_real_move!=true){	// when the cursor is hidden no need to move him
			dest.style.top=posTop+"px";
			dest.style.left=posLeft+"px";	
		}
		// usefull for smarter scroll
		dest.cursor_top=posTop;
		dest.cursor_left=posLeft;	
	//	_$(id).style.marginLeft=posLeft+"px";
	};
	
	EditArea.prototype.getLinePosTop= function(start_line){
		var elem= _$('line_'+ start_line), posTop=0;
		if( elem )
			posTop	= elem.offsetTop;
		else
			posTop	= this.lineHeight * (start_line-1);
		return posTop;
	};
	
	
	// return the dislpayed height of a text (take word-wrap into account)
	EditArea.prototype.getTextHeight= function(text){
		var t=this,elem,height;
		elem		= t.test_font_size;
		content		= text.replace(/&/g,"&amp;").replace(/</g,"&lt;");
		if( t.isIE || ( this.isOpera && this.isOpera < 9.6 ) ) {
			elem.innerHTML= "<pre>" + content.replace(/^\r?\n/, "<br>") + "</pre>";
		} else {
			elem.innerHTML= content;
		}
		height	= elem.offsetHeight;
		height	= Math.max( 1, Math.floor( elem.offsetHeight / this.lineHeight ) ) * this.lineHeight;
		return height;
	};

	/**
	 * Fix line height for the given lines
	 * @param Integer linestart
	 * @param Integer lineEnd End line or -1 to cover all lines
	 */
	EditArea.prototype.fixLinesHeight= function( textValue, lineStart,lineEnd ){
		var aText = textValue.split("\n");
		if( lineEnd == -1 )
			lineEnd	= aText.length-1;
		for( var i = Math.max(0, lineStart); i <= lineEnd; i++ )
		{
			if( elem = _$('line_'+ ( i+1 ) ) )
			{
				elem.style.height= typeof( aText[i] ) != "undefined" ? this.getTextHeight( aText[i] )+"px" : this.lineHeight;
			}
		}
	};
	
	EditArea.prototype.area_select= function(start, length){
		this.textarea.focus();
		
		start	= Math.max(0, Math.min(this.textarea.value.length, start));
		end		= Math.max(start, Math.min(this.textarea.value.length, start+length));

		if(this.isIE)
		{
			this.textarea.selectionStart	= start;
			this.textarea.selectionEnd		= end;		
			this.setIESelection();
		}
		else
		{
			// Opera bug when moving selection start and selection end
			if(this.isOpera && this.isOpera < 9.6 )
			{	
				this.textarea.setSelectionRange(0, 0);
			}
			this.textarea.setSelectionRange(start, end);
		}
		this.check_line_selection();
	};
	
	
	EditArea.prototype.area_get_selection= function(){
		var text="";
		if( document.selection ){
			var range = document.selection.createRange();
			text=range.text;
		}else{
			text= this.textarea.value.substring(this.textarea.selectionStart, this.textarea.selectionEnd);
		}
		return text;			
	};