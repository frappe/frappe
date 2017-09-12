"use strict";
(function() {

	var instanceId = 0;
	function getInstanceId() {
		return instanceId++;
	}
	// note that this function invoked from call/apply, which has "this" binded	
	function _upload(file, options) {
		options = options || {};

		var self = this;
		var socket = this.socket;
		var chunkSize = this.chunkSize;
		var transmissionDelay = this.transmissionDelay;
		var uploadId = file.uploadId;
		var uploadTo = options.uploadTo || '';
		var fileInfo = {
			id: uploadId,
			name: file.name,
			size: file.size,
			chunkSize: chunkSize,
			sent: 0
		};		

		uploadTo && (fileInfo.uploadTo = uploadTo);

		// read file
		var fileReader = new FileReader();
		fileReader.onloadend = function() {
			var buffer = fileReader.result;

			// check file mime type if exists
			if(self.accepts && self.accepts.length > 0) {
				var found = false;

				for(var i = 0; i < self.accepts.length; i++) {
					var accept = self.accepts[i];

					if(file.type === accept) {
						found = true;
						break;
					}
				}

				if(!found) {
					return self.emit('error', new Error('Not Acceptable file type ' + file.type + ' of ' + file.name + '. Type must be one of these: ' + self.accepts.join(', ')));
				}
			}

			// check file size
			if(self.maxFileSize && self.maxFileSize > 0) {
				if(file.size > +self.maxFileSize) {
					return self.emit('error', new Error('Max Uploading File size must be under ' + self.maxFileSize + ' byte(s).'));
				}
			}

			// put into uploadingFiles list
			self.uploadingFiles[uploadId] = fileInfo;

			// request the server to make a file
			self.emit('start', { 
				name: fileInfo.name, 
				size: fileInfo.size,
				uploadTo: uploadTo 
			});
			socket.emit('socket.io-file::createFile', fileInfo);

			function sendChunk() {
				if(fileInfo.aborted) {
					return;
				}

				if(fileInfo.sent >= buffer.byteLength) {
					socket.emit('socket.io-file::done::' + uploadId);
					return;
				}

				var chunk = buffer.slice(fileInfo.sent, fileInfo.sent + chunkSize);

				self.emit('stream', { 
					name: fileInfo.name, 
					size: fileInfo.size, 
					sent: fileInfo.sent,
					uploadTo: uploadTo 
				});
				socket.once('socket.io-file::request::' + uploadId, sendChunk);
				socket.emit('socket.io-file::stream::' + uploadId, chunk);

				fileInfo.sent += chunk.byteLength;
				self.uploadingFiles[uploadId] = fileInfo;
			}
			socket.once('socket.io-file::request::' + uploadId, sendChunk);
			socket.on('socket.io-file::complete::' + uploadId, function(info) {
				self.emit('complete', info);
				
				socket.removeAllListeners('socket.io-file::abort::' + uploadId);
				socket.removeAllListeners('socket.io-file::error::' + uploadId);
				socket.removeAllListeners('socket.io-file::complete::' + uploadId);

				// remove from uploadingFiles list
				delete self.uploadingFiles[uploadId];
			});
			socket.on('socket.io-file::abort::' + uploadId, function(info) {
				fileInfo.aborted = true;
				self.emit('abort', { 
					name: fileInfo.name, 
					size: fileInfo.size, 
					sent: fileInfo.sent, 
					wrote: info.wrote,
					uploadTo: uploadTo 
				});
			});
			socket.on('socket.io-file::error::' + uploadId, function(err) {
				self.emit('error', new Error(err.message));
			});
		};
		fileReader.readAsArrayBuffer(file);
	}

	function SocketIOFileClient(socket, options) {
		if(!socket) {
			return this.emit('error', new Error('SocketIOFile requires Socket.'));
		}

		this.instanceId = getInstanceId();		// using for identifying multiple file upload from SocketIOFileClient objects
		this.uploadId = 0;						// using for identifying each uploading
		this.ev = {};							// event handlers
		this.options = options || {};
		this.accepts = [];
		this.maxFileSize = undefined;
		this.socket = socket;
		this.uploadingFiles = {};

		var self = this;

		socket.once('socket.io-file::recvSync', function(settings) {
			self.maxFileSize = settings.maxFileSize || undefined;
			self.accepts = settings.accepts || [];
			self.chunkSize = settings.chunkSize || 10240;
			self.transmissionDelay = settings.transmissionDelay || 0;

			self.emit('ready');
		});
		socket.emit('socket.io-file::reqSync');
	}
	SocketIOFileClient.prototype.getUploadId = function() {
		return 'u_' + this.uploadId++;
	}
	SocketIOFileClient.prototype.upload = function(fileEl, options) {
		if(!fileEl ||
			(fileEl.files && fileEl.files.length <= 0) ||
			fileEl.length <= 0
		) {
			this.emit('error', new Error('No file(s) to upload.'));
			return [];
		}

		var self = this;
		var uploadIds = [];

		var files = fileEl.files ? fileEl.files : fileEl;
		var loaded = 0;

		for(var i = 0; i < files.length; i++) {
			var file = files[i];
			var uploadId = this.getUploadId();
			uploadIds.push(uploadId);

			file.uploadId = uploadId;

			_upload.call(self, file, options);
		}
		
		return uploadIds;
	};
	SocketIOFileClient.prototype.on = function(evName, fn) {
		if(!this.ev[evName]) {
			this.ev[evName] = [];
		}

		this.ev[evName].push(fn);
		return this;
	};
	SocketIOFileClient.prototype.off = function(evName, fn) {
		if(typeof evName === 'undefined') {
			this.ev = [];
		}
		else if(typeof fn === 'undefined') {
			if(this.ev[evName]) {
				delete this.ev[evName]; 
			}
		}
		else {
			var evList = this.ev[evName] || [];

			for(var i = 0; i < evList.length; i++) {
				if(evList[i] === fn) {
					evList = evList.splice(i, 1);
					break;
				}
			}
		}

		return this;
	};
	SocketIOFileClient.prototype.emit = function(evName, args) {
		var evList = this.ev[evName] || [];

		for(var i = 0; i < evList.length; i++) {
			evList[i](args);
		}

		return this;
	};
	SocketIOFileClient.prototype.abort = function(id) {
		var socket = this.socket;
		socket.emit('socket.io-file::abort::' + id);
	};
	SocketIOFileClient.prototype.destroy = function() {
		var uploadingFiles = this.uploadingFiles;

		for(var key in uploadingFiles) {
			this.abort(key);
		}

		this.socket = null;
		this.uploadingFiles = null;
		this.ev = null;
	};
	SocketIOFileClient.prototype.getUploadInfo = function() {
		return JSON.parse(JSON.stringify(this.uploadingFiles));
	};

	// module export
	// CommonJS
	if (typeof exports === "object" && typeof module !== "undefined") {
		module.exports = SocketIOFileClient;
	}
	// RequireJS
	else if (typeof define === "function" && define.amd) {
		define(['SocketIOFileClient'], SocketIOFileClient);
	}
	else {
		var g;

		if (typeof window !== "undefined") {
			g = window;
		}
		else if (typeof global !== "undefined") {
			g = global;
		}
		else if (typeof self !== "undefined") {
			g = self;
		}

		g.SocketIOFileClient = SocketIOFileClient;
	}
})();