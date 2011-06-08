	EditArea.prototype.show_search = function(){
		if(_$("area_search_replace").style.visibility=="visible"){
			this.hidden_search();
		}else{
			this.open_inline_popup("area_search_replace");
			var text= this.area_get_selection();
			var search= text.split("\n")[0];
			_$("area_search").value= search;
			_$("area_search").focus();
		}
	};
	
	EditArea.prototype.hidden_search= function(){
		/*_$("area_search_replace").style.visibility="hidden";
		this.textarea.focus();
		var icon= _$("search");
		setAttribute(icon, "class", getAttribute(icon, "class").replace(/ selected/g, "") );*/
		this.close_inline_popup("area_search_replace");
	};
	
	EditArea.prototype.area_search= function(mode){
		
		if(!mode)
			mode="search";
		_$("area_search_msg").innerHTML="";		
		var search=_$("area_search").value;		
		
		this.textarea.focus();		
		this.textarea.textareaFocused=true;
		
		var infos= this.get_selection_infos();	
		var start= infos["selectionStart"];
		var pos=-1;
		var pos_begin=-1;
		var length=search.length;
		
		if(_$("area_search_replace").style.visibility!="visible"){
			this.show_search();
			return;
		}
		if(search.length==0){
			_$("area_search_msg").innerHTML=this.get_translation("search_field_empty");
			return;
		}
		// advance to the next occurence if no text selected
		if(mode!="replace" ){
			if(_$("area_search_reg_exp").checked)
				start++;
			else
				start+= search.length;
		}
		
		//search
		if(_$("area_search_reg_exp").checked){
			// regexp search
			var opt="m";
			if(!_$("area_search_match_case").checked)
				opt+="i";
			var reg= new RegExp(search, opt);
			pos= infos["full_text"].substr(start).search(reg);
			pos_begin= infos["full_text"].search(reg);
			if(pos!=-1){
				pos+=start;
				length=infos["full_text"].substr(start).match(reg)[0].length;
			}else if(pos_begin!=-1){
				length=infos["full_text"].match(reg)[0].length;
			}
		}else{
			if(_$("area_search_match_case").checked){
				pos= infos["full_text"].indexOf(search, start); 
				pos_begin= infos["full_text"].indexOf(search); 
			}else{
				pos= infos["full_text"].toLowerCase().indexOf(search.toLowerCase(), start); 
				pos_begin= infos["full_text"].toLowerCase().indexOf(search.toLowerCase()); 
			}		
		}
		
		// interpret result
		if(pos==-1 && pos_begin==-1){
			_$("area_search_msg").innerHTML="<strong>"+search+"</strong> "+this.get_translation("not_found");
			return;
		}else if(pos==-1 && pos_begin != -1){
			begin= pos_begin;
			_$("area_search_msg").innerHTML=this.get_translation("restart_search_at_begin");
		}else
			begin= pos;
		
		//_$("area_search_msg").innerHTML+="<strong>"+search+"</strong> found at "+begin+" strat at "+start+" pos "+pos+" curs"+ infos["indexOfCursor"]+".";
		if(mode=="replace" && pos==infos["indexOfCursor"]){
			var replace= _$("area_replace").value;
			var new_text="";			
			if(_$("area_search_reg_exp").checked){
				var opt="m";
				if(!_$("area_search_match_case").checked)
					opt+="i";
				var reg= new RegExp(search, opt);
				new_text= infos["full_text"].substr(0, begin) + infos["full_text"].substr(start).replace(reg, replace);
			}else{
				new_text= infos["full_text"].substr(0, begin) + replace + infos["full_text"].substr(begin + length);
			}
			this.textarea.value=new_text;
			this.area_select(begin, length);
			this.area_search();
		}else
			this.area_select(begin, length);
	};
	
	
	
	
	EditArea.prototype.area_replace= function(){		
		this.area_search("replace");
	};
	
	EditArea.prototype.area_replace_all= function(){
	/*	this.area_select(0, 0);
		_$("area_search_msg").innerHTML="";
		while(_$("area_search_msg").innerHTML==""){
			this.area_replace();
		}*/
	
		var base_text= this.textarea.value;
		var search= _$("area_search").value;		
		var replace= _$("area_replace").value;
		if(search.length==0){
			_$("area_search_msg").innerHTML=this.get_translation("search_field_empty");
			return ;
		}
		
		var new_text="";
		var nb_change=0;
		if(_$("area_search_reg_exp").checked){
			// regExp
			var opt="mg";
			if(!_$("area_search_match_case").checked)
				opt+="i";
			var reg= new RegExp(search, opt);
			nb_change= infos["full_text"].match(reg).length;
			new_text= infos["full_text"].replace(reg, replace);
			
		}else{
			
			if(_$("area_search_match_case").checked){
				var tmp_tab=base_text.split(search);
				nb_change= tmp_tab.length -1 ;
				new_text= tmp_tab.join(replace);
			}else{
				// case insensitive
				var lower_value=base_text.toLowerCase();
				var lower_search=search.toLowerCase();
				
				var start=0;
				var pos= lower_value.indexOf(lower_search);				
				while(pos!=-1){
					nb_change++;
					new_text+= this.textarea.value.substring(start , pos)+replace;
					start=pos+ search.length;
					pos= lower_value.indexOf(lower_search, pos+1);
				}
				new_text+= this.textarea.value.substring(start);				
			}
		}			
		if(new_text==base_text){
			_$("area_search_msg").innerHTML="<strong>"+search+"</strong> "+this.get_translation("not_found");
		}else{
			this.textarea.value= new_text;
			_$("area_search_msg").innerHTML="<strong>"+nb_change+"</strong> "+this.get_translation("occurrence_replaced");
			// firefox and opera doesn't manage with the focus if it's done directly
			//editArea.textarea.focus();editArea.textarea.textareaFocused=true;
			setTimeout("editArea.textarea.focus();editArea.textarea.textareaFocused=true;", 100);
		}
		
		
	};
