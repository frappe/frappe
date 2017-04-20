import subprocess

def execute():
    subprocess.call([
        'npm', 'install',
        'babel-core',
        'chokidar',
        'babel-preset-es2015',
        'babel-preset-es2016',
        'babel-preset-es2017',
        'babel-preset-babili'
    ])