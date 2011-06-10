<?php
	/******
	 *
	 *	EditArea PHP compressor
	 * 	Developped by Christophe Dolivet
	 *	Released under LGPL, Apache and BSD licenses
	 *	v1.1.3 (2007/01/18)	 
	 *
	******/
	
	// CONFIG
	$param['cache_duration']= 3600 * 24 * 10;		// 10 days util client cache expires
	$param['compress'] = true;						// enable the code compression, should be activated but it can be usefull to desactivate it for easier error retrieving (true or false)
	$param['debug'] = false;						// Enable this option if you need debuging info
	$param['use_disk_cache']= true;					// If you enable this option gzip files will be cached on disk.
	$param['use_gzip']= true;						// Enable gzip compression
	// END CONFIG
	
	$compressor= new Compressor($param);
	
	class Compressor{
	
		
		function compressor($param)
		{
			$this->__construct($param);
		}
		
		function __construct($param)
		{
			$this->start_time= $this->get_microtime();
			$this->file_loaded_size=0;
			$this->param= $param;
			$this->script_list="";
			$this->path= dirname(__FILE__)."/";
			if(isset($_GET['plugins'])){
				$this->load_all_plugins= true;
				$this->full_cache_file= $this->path."edit_area_full_with_plugins.js";
				$this->gzip_cache_file= $this->path."edit_area_full_with_plugins.gz";
			}else{
				$this->load_all_plugins= false;
				$this->full_cache_file= $this->path."edit_area_full.js";
				$this->gzip_cache_file= $this->path."edit_area_full.gz";
			}
			
			$this->check_gzip_use();
			$this->send_headers();
			$this->check_cache();
			$this->load_files();
			$this->send_datas();
		}
		
		function send_headers()
		{
			header("Content-type: text/javascript; charset: UTF-8");
			header("Vary: Accept-Encoding"); // Handle proxies
			header(sprintf("Expires: %s GMT", gmdate("D, d M Y H:i:s", time() + $this->param['cache_duration'])) );
			if($this->use_gzip)
				header("Content-Encoding: ".$this->gzip_enc_header);
		}
		
		function check_gzip_use()
		{
			$encodings = array();
			$desactivate_gzip=false;
					
			if (isset($_SERVER['HTTP_ACCEPT_ENCODING']))
				$encodings = explode(',', strtolower(preg_replace("/\s+/", "", $_SERVER['HTTP_ACCEPT_ENCODING'])));
			
			// desactivate gzip for IE version < 7
			if(preg_match("/(?:msie )([0-9.]+)/i", $_SERVER['HTTP_USER_AGENT'], $ie))
			{
				if($ie[1]<7)
					$desactivate_gzip=true;	
			}
			
			// Check for gzip header or northon internet securities
			if (!$desactivate_gzip && $this->param['use_gzip'] && (in_array('gzip', $encodings) || in_array('x-gzip', $encodings) || isset($_SERVER['---------------'])) && function_exists('ob_gzhandler') && !ini_get('zlib.output_compression')) {
				$this->gzip_enc_header= in_array('x-gzip', $encodings) ? "x-gzip" : "gzip";
				$this->use_gzip=true;
				$this->cache_file=$this->gzip_cache_file;
			}else{
				$this->use_gzip=false;
				$this->cache_file=$this->full_cache_file;
			}
		}
		
		function check_cache()
		{
			// Only gzip the contents if clients and server support it
			if (file_exists($this->cache_file)) {
				// check if cache file must be updated
				$cache_date=0;				
				if ($dir = opendir($this->path)) {
					while (($file = readdir($dir)) !== false) {
						if(is_file($this->path.$file) && $file!="." && $file!="..")
							$cache_date= max($cache_date, filemtime($this->path.$file));
					}
					closedir($dir);
				}
				if($this->load_all_plugins){
					$plug_path= $this->path."plugins/";
					if (($dir = @opendir($plug_path)) !== false)
					{
						while (($file = readdir($dir)) !== false)
						{
							if ($file !== "." && $file !== "..")
							{
								if(is_dir($plug_path.$file) && file_exists($plug_path.$file."/".$file.".js"))
									$cache_date= max($cache_date, filemtime("plugins/".$file."/".$file.".js"));
							}
						}
						closedir($dir);
					}
				}

				if(filemtime($this->cache_file) >= $cache_date){
					// if cache file is up to date
					$last_modified = gmdate("D, d M Y H:i:s",filemtime($this->cache_file))." GMT";
					if (isset($_SERVER["HTTP_IF_MODIFIED_SINCE"]) && strcasecmp($_SERVER["HTTP_IF_MODIFIED_SINCE"], $last_modified) === 0)
					{
						header("HTTP/1.1 304 Not Modified");
						header("Last-modified: ".$last_modified);
						header("Cache-Control: Public"); // Tells HTTP 1.1 clients to cache
						header("Pragma:"); // Tells HTTP 1.0 clients to cache
					}
					else
					{
						header("Last-modified: ".$last_modified);
						header("Cache-Control: Public"); // Tells HTTP 1.1 clients to cache
						header("Pragma:"); // Tells HTTP 1.0 clients to cache
						header('Content-Length: '.filesize($this->cache_file));
						echo file_get_contents($this->cache_file);
					}				
					die;
				}
			}
			return false;
		}
		
		function load_files()
		{
			$loader= $this->get_content("edit_area_loader.js")."\n";
			
			// get the list of other files to load
	    	$loader= preg_replace("/(t\.scripts_to_load=\s*)\[([^\]]*)\];/e"
						, "\$this->replace_scripts('script_list', '\\1', '\\2')"
						, $loader);
		
			$loader= preg_replace("/(t\.sub_scripts_to_load=\s*)\[([^\]]*)\];/e"
						, "\$this->replace_scripts('sub_script_list', '\\1', '\\2')"
						, $loader);

			$this->datas= $loader;
			$this->compress_javascript($this->datas);
			
			// load other scripts needed for the loader
			preg_match_all('/"([^"]*)"/', $this->script_list, $match);
			foreach($match[1] as $key => $value)
			{
				$content= $this->get_content(preg_replace("/\\|\//i", "", $value).".js");
				$this->compress_javascript($content);
				$this->datas.= $content."\n";
			}
			//$this->datas);
			//$this->datas= preg_replace('/(( |\t|\r)*\n( |\t)*)+/s', "", $this->datas);
			
			// improved compression step 1/2	
			$this->datas= preg_replace(array("/(\b)EditAreaLoader(\b)/", "/(\b)editAreaLoader(\b)/", "/(\b)editAreas(\b)/"), array("EAL", "eAL", "eAs"), $this->datas);
			//$this->datas= str_replace(array("EditAreaLoader", "editAreaLoader", "editAreas"), array("EAL", "eAL", "eAs"), $this->datas);
			$this->datas.= "var editAreaLoader= eAL;var editAreas=eAs;EditAreaLoader=EAL;";
		
			// load sub scripts
			$sub_scripts="";
			$sub_scripts_list= array();
			preg_match_all('/"([^"]*)"/', $this->sub_script_list, $match);
			foreach($match[1] as $value){
				$sub_scripts_list[]= preg_replace("/\\|\//i", "", $value).".js";
			}
		
			if($this->load_all_plugins){
				// load plugins scripts
				$plug_path= $this->path."plugins/";
				if (($dir = @opendir($plug_path)) !== false)
				{
					while (($file = readdir($dir)) !== false)
					{
						if ($file !== "." && $file !== "..")
						{
							if(is_dir($plug_path.$file) && file_exists($plug_path.$file."/".$file.".js"))
								$sub_scripts_list[]= "plugins/".$file."/".$file.".js";
						}
					}
					closedir($dir);
				}
			}
							
			foreach($sub_scripts_list as $value){
				$sub_scripts.= $this->get_javascript_content($value);
			}
			// improved compression step 2/2	
			$sub_scripts= preg_replace(array("/(\b)editAreaLoader(\b)/", "/(\b)editAreas(\b)/", "/(\b)editArea(\b)/", "/(\b)EditArea(\b)/"), array("eAL", "eAs", "eA", "EA"), $sub_scripts);
		//	$sub_scripts= str_replace(array("editAreaLoader", "editAreas", "editArea", "EditArea"), array("eAL", "eAs", "eA", "EA"), $sub_scripts);
			$sub_scripts.= "var editArea= eA;EditArea=EA;";
			
			
			// add the scripts
		//	$this->datas.= sprintf("editAreaLoader.iframe_script= \"<script type='text/javascript'>%s</script>\";\n", $sub_scripts);
		
		
			// add the script and use a last compression 
			if( $this->param['compress'] )
			{
				$last_comp	= array( 'Á' => 'this',
								 'Â' => 'textarea',
								 'Ã' => 'function',
								 'Ä' => 'prototype',
								 'Å' => 'settings',
								 'Æ' => 'length',
								 'Ç' => 'style',
								 'È' => 'parent',
								 'É' => 'last_selection',
								 'Ê' => 'value',
								 'Ë' => 'true',
								 'Ì' => 'false'
								 /*,
									'Î' => '"',
								 'Ï' => "\n",
								 'À' => "\r"*/);
			}
			else
			{
				$last_comp	= array();
			}
			
			$js_replace= '';
			foreach( $last_comp as $key => $val )
				$js_replace .= ".replace(/". $key ."/g,'". str_replace( array("\n", "\r"), array('\n','\r'), $val ) ."')";
			
			$this->datas.= sprintf("editAreaLoader.iframe_script= \"<script type='text/javascript'>%s</script>\"%s;\n",
								str_replace( array_values($last_comp), array_keys($last_comp), $sub_scripts ), 
								$js_replace);
			
			if($this->load_all_plugins)
				$this->datas.="editAreaLoader.all_plugins_loaded=true;\n";
		
			
			// load the template
			$this->datas.= sprintf("editAreaLoader.template= \"%s\";\n", $this->get_html_content("template.html"));
			// load the css
			$this->datas.= sprintf("editAreaLoader.iframe_css= \"<style>%s</style>\";\n", $this->get_css_content("edit_area.css"));
					
		//	$this->datas= "function editArea(){};editArea.prototype.loader= function(){alert('bouhbouh');} var a= new editArea();a.loader();";
					
		}
		
		function send_datas()
		{
			if($this->param['debug']){
				$header=sprintf("/* USE PHP COMPRESSION\n");
				$header.=sprintf("javascript size: based files: %s => PHP COMPRESSION => %s ", $this->file_loaded_size, strlen($this->datas));
				if($this->use_gzip){
					$gzip_datas=  gzencode($this->datas, 9, FORCE_GZIP);				
					$header.=sprintf("=> GZIP COMPRESSION => %s", strlen($gzip_datas));
					$ratio = round(100 - strlen($gzip_datas) / $this->file_loaded_size * 100.0);			
				}else{
					$ratio = round(100 - strlen($this->datas) / $this->file_loaded_size * 100.0);
				}
				$header.=sprintf(", reduced by %s%%\n", $ratio);
				$header.=sprintf("compression time: %s\n", $this->get_microtime()-$this->start_time); 
				$header.=sprintf("%s\n", implode("\n", $this->infos));
				$header.=sprintf("*/\n");
				$this->datas= $header.$this->datas;	
			}
			$mtime= time(); // ensure that the 2 disk files will have the same update time
			// generate gzip file and cahce it if using disk cache
			if($this->use_gzip){
				$this->gzip_datas= gzencode($this->datas, 9, FORCE_GZIP);
				if($this->param['use_disk_cache'])
					$this->file_put_contents($this->gzip_cache_file, $this->gzip_datas, $mtime);
			}
			
			// generate full js file and cache it if using disk cache			
			if($this->param['use_disk_cache'])
				$this->file_put_contents($this->full_cache_file, $this->datas, $mtime);
			
			// generate output
			if($this->use_gzip)
				echo $this->gzip_datas;
			else
				echo $this->datas;
				
//			die;
		}
				
		
		function get_content($end_uri)
		{
			$end_uri=preg_replace("/\.\./", "", $end_uri); // Remove any .. (security)
			$file= $this->path.$end_uri;
			if(file_exists($file)){
				$this->infos[]=sprintf("'%s' loaded", $end_uri);
				/*$fd = fopen($file, 'rb');
				$content = fread($fd, filesize($file));
				fclose($fd);
				return $content;*/
				return $this->file_get_contents($file);
			}else{
				$this->infos[]=sprintf("'%s' not loaded", $end_uri);
				return "";
			}
		}
		
		function get_javascript_content($end_uri)
		{
			$val=$this->get_content($end_uri);
	
			$this->compress_javascript($val);
			$this->prepare_string_for_quotes($val);
			return $val;
		}
		
		function compress_javascript(&$code)
		{
			if($this->param['compress'])
			{
				// remove all comments
				//	(\"(?:[^\"\\]*(?:\\\\)*(?:\\\"?)?)*(?:\"|$))|(\'(?:[^\'\\]*(?:\\\\)*(?:\\'?)?)*(?:\'|$))|(?:\/\/(?:.|\r|\t)*?(\n|$))|(?:\/\*(?:.|\n|\r|\t)*?(?:\*\/|$))
				$code= preg_replace("/(\"(?:[^\"\\\\]*(?:\\\\\\\\)*(?:\\\\\"?)?)*(?:\"|$))|(\'(?:[^\'\\\\]*(?:\\\\\\\\)*(?:\\\\\'?)?)*(?:\'|$))|(?:\/\/(?:.|\r|\t)*?(\n|$))|(?:\/\*(?:.|\n|\r|\t)*?(?:\*\/|$))/s", "$1$2$3", $code);
				// remove line return, empty line and tabulation
				$code= preg_replace('/(( |\t|\r)*\n( |\t)*)+/s', " ", $code);
				// add line break before "else" otherwise navigators can't manage to parse the file
				$code= preg_replace('/(\b(else)\b)/', "\n$1", $code);
				// remove unnecessary spaces
				$code= preg_replace('/( |\t|\r)*(;|\{|\}|=|==|\-|\+|,|\(|\)|\|\||&\&|\:)( |\t|\r)*/', "$2", $code);
			}
		}
		
		function get_css_content($end_uri){
			$code=$this->get_content($end_uri);
			// remove comments
			$code= preg_replace("/(?:\/\*(?:.|\n|\r|\t)*?(?:\*\/|$))/s", "", $code);
			// remove spaces
			$code= preg_replace('/(( |\t|\r)*\n( |\t)*)+/s', "", $code);
			// remove spaces
			$code= preg_replace('/( |\t|\r)?(\:|,|\{|\})( |\t|\r)+/', "$2", $code);
		
			$this->prepare_string_for_quotes($code);
			return $code;
		}
		
		function get_html_content($end_uri){
			$code=$this->get_content($end_uri);
			//$code= preg_replace('/(\"(?:\\\"|[^\"])*(?:\"|$))|' . "(\'(?:\\\'|[^\'])*(?:\'|$))|(?:\/\/(?:.|\r|\t)*?(\n|$))|(?:\/\*(?:.|\n|\r|\t)*?(?:\*\/|$))/s", "$1$2$3", $code);
			$code= preg_replace('/(( |\t|\r)*\n( |\t)*)+/s', " ", $code);
			$this->prepare_string_for_quotes($code);
			return $code;
		}
		
		function prepare_string_for_quotes(&$str){
			// prepare the code to be putted into quotes 
			/*$pattern= array("/(\\\\)?\"/", '/\\\n/'	, '/\\\r/'	, "/(\r?\n)/");
			$replace= array('$1$1\\"', '\\\\\\n', '\\\\\\r'	, '\\\n"$1+"');*/
			$pattern= array("/(\\\\)?\"/", '/\\\n/'	, '/\\\r/'	, "/(\r?\n)/");
			if($this->param['compress'])
				$replace= array('$1$1\\"', '\\\\\\n', '\\\\\\r'	, '\n');
			else
				$replace= array('$1$1\\"', '\\\\\\n', '\\\\\\r'	, "\\n\"\n+\"");
			$str= preg_replace($pattern, $replace, $str);
		}
		
		function replace_scripts($var, $param1, $param2)
		{
			$this->$var=stripslashes($param2);
	        return $param1."[];";
		}

		/* for php version that have not thoses functions */
		function file_get_contents($file)
		{
			$fd = fopen($file, 'rb');
			$content = fread($fd, filesize($file));
			fclose($fd);
			$this->file_loaded_size+= strlen($content);
			return $content;				
		}
		
		function file_put_contents($file, &$content, $mtime=-1)
		{
			if($mtime==-1)
				$mtime=time();
			$fp = @fopen($file, "wb");
			if ($fp) {
				fwrite($fp, $content);
				fclose($fp);
				touch($file, $mtime);
				return true;
			}
			return false;
		}
		
		function get_microtime()
		{
		   list($usec, $sec) = explode(" ", microtime());
		   return ((float)$usec + (float)$sec);
		}
	}	
?>
