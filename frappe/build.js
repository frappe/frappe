var path = require('path');
var fs = require('fs');
var babel = require('babel-core');
var less = require('less');
var p = path.resolve;

var sites_folder = __dirname + '/../../../sites/';
var apps_folder = __dirname + '/../../../apps/';
var contents = fs.readFileSync(sites_folder + 'apps.txt', 'utf8');
var apps = contents.split("\n");

function bundle() {
    const build_map = make_build_map();

    babelify(build_map);
}



function compile_less() {
    for(const app of apps) {

        const public_path = p(get_app_path(app), 'public');
        const less_path = p(public_path, 'less');

        if (!fs.existsSync(less_path)) continue;
        const files = fs.readdirSync(less_path);

        for(const file of files) {
            compile_less_file(file, less_path, public_path);
        }
    }
    watch_less();
}

compile_less();

function compile_less_file(file, less_path, public_path) {

    const file_content = fs.readFileSync(p(less_path, file), 'utf8');
    const output_file = file.split('.')[0] + '.css';

    less.render(file_content, {
        paths: [ p(less_path) ],
        outputDir: p(public_path, 'css'),
        filename: file,
        compress: true
    }, (e, res) => {
        if(!e) {
            fs.writeFileSync(p(public_path, 'css', output_file), res.css)
            console.log(output_file, ' compiled');
        } else {
            console.log(e, css)
        }
    })
}

function watch_less() {
    const less_paths = apps.map((app) => p(get_app_path(app), 'public', 'less'));
    // console.log(less_paths)
    for(const less_path of less_paths) {
        const public_path = p(less_path, '..');
        if(!fs.existsSync(less_path)) continue;
        fs.watch(p(less_path), (e, filename) => {
            console.log(filename, ' changed');
            compile_less_file(filename, less_path, public_path);
        });
    }
}
// bundle();

function make_build_map() {
    const build_map = {}
    for (const app of apps) {
        var build_json_path = get_app_path(app) + '/public/build.json';
        if (!fs.existsSync(build_json_path)) continue;

        const build_json = fs.readFileSync(build_json_path);
        const build_files = JSON.parse(build_json);

        for (const target in build_files) {
            const sources = build_files[target];
            // console.log(target, sources)
            const new_sources = []
            for (const s of sources) {

                // console.log(s)
                if (s.startsWith('public')) {

                    const split = s.split('public');
                    split.shift();
                    const new_src = split.join('public')

                    new_sources.push(sites_folder + 'assets/' + app + new_src)
                }

            }

            if (new_sources.length)
                build_files[target] = new_sources;
            else
                delete build_files[target]
        }

        const build_files_new = {};

        for (const key in build_files) {
            const value = build_files[key];
            build_files_new[sites_folder + 'assets/' + key] = value;
        }

        Object.assign(build_map, build_files_new)
    }

    return build_map;
}

function get_app_path(app) {
    return apps_folder + '/' + app + '/' + app;
}

function babelify(build_map) {

    for(const output_path in build_map) {
        const inputs = build_map[output_path];

        if(output_path.endsWith('.css'))
            continue;

        let output_txt = "";
        for(const file of inputs) {
            let file_content = fs.readFileSync(file, "utf-8");
            
            if(file.endsWith('.html')) {
                file_content = html_to_js_template(file, file_content);
            }
            
            output_txt += "\n" + file_content;
        }

        try {
            output_txt = babel.transform(output_txt, {
                presets: ['es2015']
            }).code;
            console.log(output_path, ' >> success');
        } catch(e) {
            console.log(output_path, ' failed');
            console.log('because of ', e);
        }

        // babel.tran

        fs.writeFile(output_path, output_txt, function(c) {
            console.log(output_path, 'written');
            // console.log(output, '>> success');
        });
    }

}

function html_to_js_template(path, content) {
    var key = path.split("/");
    key = key[key.length - 1]
    key = key.split('.')[0]

    content = scrub_html_template(content)
    return `frappe.templates["${key}"] = '${content}';\n`;
}

function scrub_html_template(content) {
    content = content.replace(/\s/g, " ");
    content = content.replace(/(<!--.*?-->)/g, "");
    return content.replace("'", "\'");
}