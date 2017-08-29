var express = require('express');
var path = require('path');
var app = express();
var http = require('http').Server(app);
const port = process.env.NODE_PORT || 9001;

const { get_boot } = require('./boot');

var assets_path = path.resolve('sites/assets');
var frappe_path = path.resolve('apps/frappe');

app.use('/assets', express.static(assets_path));

app.use('/', express.static(path.resolve(frappe_path, 'frappe', 'node', 'www'), {
	extensions: ['html']
}));

app.post('/api/auth', (req, res) => {
	res.send({
		message: true
	});
});

app.get('/api/boot', async (req, res) => {
	const boot = await get_boot();
	res.json({
		message: boot
	});

});

// serve socketio
http.listen(port, function() {
	console.log('listening on *:', port); //eslint-disable-line
});

// test route
app.get('/', function(req, res) {
	res.sendfile('index.html');
});
