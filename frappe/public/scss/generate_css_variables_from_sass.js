const fs = require('fs')
const path = require('path')
const args = {}

process.argv
    .slice(2)
    .map((v, i) => {
        if (v.startsWith('--')) {
            const key = v.slice(2)
            args[key] = process.argv[(i + 2) + 1]
        }
    });

run({
    src: '/Users/netchampfaris/frappe-bench3/apps/frappe/node_modules/bootstrap/scss/_variables.scss',
    outpath: '/Users/netchampfaris/frappe-bench3/apps/frappe/frappe/public/scss/css_variables.scss'
})


function run({ src: file_path, outpath }) {
    const blacklisted_keywords = ['grid-columns',
        '() !default', 'true !default', 'false !default', 'table-border-width',
        'yiq', 'table-bg-level', 'theme-color-interval'
    ]

    const filecontents = fs.readFileSync(file_path, { encoding: 'utf-8' })
    const output  = [];

    const lineSplit = filecontents.split('\n');

    for (let line of lineSplit) {
        if (line.startsWith('$') && line.endsWith(';') && !blacklisted_keywords.some(k => line.includes(k))) {
            const match = line.match(/\$([\w\-]+):/);
            if (match) {
                const variable_name = match[1];
                const output_line = `$${variable_name}: var(--${variable_name}, $${variable_name});`
                output.push(output_line);
            }
        }
    }

    const outputContent = output.join('\n');
    fs.writeFileSync(outpath, outputContent, { encoding: 'utf-8' })
}
