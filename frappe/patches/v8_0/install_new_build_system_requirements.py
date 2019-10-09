from __future__ import print_function, unicode_literals
from subprocess import Popen, call, PIPE

def execute():
    # update nodejs version if brew exists
    p = Popen(['which', 'brew'], stdout=PIPE, stderr=PIPE)
    output, err = p.communicate()
    if output:
        call(['brew', 'upgrade', 'node'])
    else:
        print('Please update your NodeJS version')

    call([
        'npm', 'install',
        'babel-core',
        'less',
        'chokidar',
        'babel-preset-es2015',
        'babel-preset-es2016',
        'babel-preset-es2017',
        'babel-preset-babili'
    ])