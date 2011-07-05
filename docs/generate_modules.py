#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
sphinx-autopackage-script

This script parses a directory tree looking for python modules and packages and
creates ReST files appropriately to create code documentation with Sphinx.
It also creates a modules index (named modules.<suffix>).
"""

# Copyright 2008 Société des arts technologiques (SAT), http://www.sat.qc.ca/
# Copyright 2010 Thomas Waldmann <tw AT waldmann-edv DOT de>
# All rights reserved.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import os
import optparse


# automodule options
OPTIONS = ['members',
           'undoc-members',
           # 'inherited-members', # disabled because there's a bug in sphinx
           'show-inheritance',
          ]

INIT = '__init__.py'

def makename(package, module):
    """Join package and module with a dot."""
    # Both package and module can be None/empty.
    if package:
        name = package
        if module:
            name += '.' + module
    else:
        name = module
    return name

def write_file(name, text, opts):
    """Write the output file for module/package <name>."""
    if opts.dryrun:
        return
    fname = os.path.join(opts.destdir, "%s.%s" % (name, opts.suffix))
    if not opts.force and os.path.isfile(fname):
        print 'File %s already exists, skipping.' % fname
    else:
        print 'Creating file %s.' % fname
        f = open(fname, 'w')
        f.write(text)
        f.close()

def format_heading(level, text):
    """Create a heading of <level> [1, 2 or 3 supported]."""
    underlining = ['=', '-', '~', ][level-1] * len(text)
    return '%s\n%s\n\n' % (text, underlining)

def format_directive(module, package=None):
    """Create the automodule directive and add the options."""
    directive = '.. automodule:: %s\n' % makename(package, module)
    for option in OPTIONS:
        directive += '    :%s:\n' % option
    return directive

def create_module_file(package, module, opts):
    """Build the text of the file and write the file."""
    text = format_heading(1, '%s Module' % module)
    text += format_heading(2, ':mod:`%s` Module' % module)
    text += format_directive(module, package)
    write_file(makename(package, module), text, opts)

def create_package_file(root, master_package, subroot, py_files, opts, subs):
    """Build the text of the file and write the file."""
    package = os.path.split(root)[-1]
    text = format_heading(1, '%s Package' % package)
    # add each package's module
    for py_file in py_files:
        if shall_skip(os.path.join(root, py_file)):
            continue
        is_package = py_file == INIT
        py_file = os.path.splitext(py_file)[0]
        py_path = makename(subroot, py_file)
        if is_package:
            heading = ':mod:`%s` Package' % package
        else:
            heading = ':mod:`%s` Module' % py_file
        text += format_heading(2, heading)
        text += format_directive(is_package and subroot or py_path, master_package)
        text += '\n'

    # build a list of directories that are packages (they contain an INIT file)
    subs = [sub for sub in subs if os.path.isfile(os.path.join(root, sub, INIT))]
    # if there are some package directories, add a TOC for theses subpackages
    if subs:
        text += format_heading(2, 'Subpackages')
        text += '.. toctree::\n\n'
        for sub in subs:
            text += '    %s.%s\n' % (makename(master_package, subroot), sub)
        text += '\n'

    write_file(makename(master_package, subroot), text, opts)

def create_modules_toc_file(master_package, modules, opts, name='modules'):
    """
    Create the module's index.
    """
    text = format_heading(1, '%s Modules' % opts.header)
    text += '.. toctree::\n'
    text += '   :maxdepth: %s\n\n' % opts.maxdepth

    modules.sort()
    prev_module = ''
    for module in modules:
        # look if the module is a subpackage and, if yes, ignore it
        if module.startswith(prev_module + '.'):
            continue
        prev_module = module
        text += '   %s\n' % module

    write_file(name, text, opts)

def shall_skip(module):
    """
    Check if we want to skip this module.
    """
    # skip it, if there is nothing (or just \n or \r\n) in the file
    return os.path.getsize(module) < 3

def recurse_tree(path, excludes, opts):
    """
    Look for every file in the directory tree and create the corresponding
    ReST files.
    """
    # use absolute path for root, as relative paths like '../../foo' cause
    # 'if "/." in root ...' to filter out *all* modules otherwise
    path = os.path.abspath(path)
    # check if the base directory is a package and get is name
    if INIT in os.listdir(path):
        package_name = path.split(os.path.sep)[-1]
    else:
        package_name = None

    toc = []
    tree = os.walk(path, False)
    for root, subs, files in tree:
        # keep only the Python script files
        py_files =  sorted([f for f in files if os.path.splitext(f)[1] == '.py'])
        if INIT in py_files:
            py_files.remove(INIT)
            py_files.insert(0, INIT)
        # remove hidden ('.') and private ('_') directories
        subs = sorted([sub for sub in subs if sub[0] not in ['.', '_']])
        # check if there are valid files to process
        # TODO: could add check for windows hidden files
        if "/." in root or "/_" in root \
        or not py_files \
        or is_excluded(root, excludes):
            continue
        if INIT in py_files:
            # we are in package ...
            if (# ... with subpackage(s)
                subs
                or
                # ... with some module(s)
                len(py_files) > 1
                or
                # ... with a not-to-be-skipped INIT file
                not shall_skip(os.path.join(root, INIT))
               ):
                subroot = root[len(path):].lstrip(os.path.sep).replace(os.path.sep, '.')
                create_package_file(root, package_name, subroot, py_files, opts, subs)
                toc.append(makename(package_name, subroot))
        elif root == path:
            # if we are at the root level, we don't require it to be a package
            for py_file in py_files:
                if not shall_skip(os.path.join(path, py_file)):
                    module = os.path.splitext(py_file)[0]
                    create_module_file(package_name, module, opts)
                    toc.append(makename(package_name, module))

    # create the module's index
    if not opts.notoc:
        create_modules_toc_file(package_name, toc, opts)

def normalize_excludes(rootpath, excludes):
    """
    Normalize the excluded directory list:
    * must be either an absolute path or start with rootpath,
    * otherwise it is joined with rootpath
    * with trailing slash
    """
    sep = os.path.sep
    f_excludes = []
    for exclude in excludes:
        if not os.path.isabs(exclude) and not exclude.startswith(rootpath):
            exclude = os.path.join(rootpath, exclude)
        if not exclude.endswith(sep):
            exclude += sep
        f_excludes.append(exclude)
    return f_excludes

def is_excluded(root, excludes):
    """
    Check if the directory is in the exclude list.

    Note: by having trailing slashes, we avoid common prefix issues, like
          e.g. an exlude "foo" also accidentally excluding "foobar".
    """
    sep = os.path.sep
    if not root.endswith(sep):
        root += sep
    for exclude in excludes:
        if root.startswith(exclude):
            return True
    return False

def main():
    """
    Parse and check the command line arguments.
    """
    parser = optparse.OptionParser(usage="""usage: %prog [options] <package path> [exclude paths, ...]

Note: By default this script will not overwrite already created files.""")
    parser.add_option("-n", "--doc-header", action="store", dest="header", help="Documentation Header (default=Project)", default="Project")
    parser.add_option("-d", "--dest-dir", action="store", dest="destdir", help="Output destination directory", default="")
    parser.add_option("-s", "--suffix", action="store", dest="suffix", help="module suffix (default=txt)", default="txt")
    parser.add_option("-m", "--maxdepth", action="store", dest="maxdepth", help="Maximum depth of submodules to show in the TOC (default=4)", type="int", default=4)
    parser.add_option("-r", "--dry-run", action="store_true", dest="dryrun", help="Run the script without creating the files")
    parser.add_option("-f", "--force", action="store_true", dest="force", help="Overwrite all the files")
    parser.add_option("-t", "--no-toc", action="store_true", dest="notoc", help="Don't create the table of content file")
    (opts, args) = parser.parse_args()
    if not args:
        parser.error("package path is required.")
    else:
        rootpath, excludes = args[0], args[1:]
        if os.path.isdir(rootpath):
            # check if the output destination is a valid directory
            if opts.destdir and os.path.isdir(opts.destdir):
                excludes = normalize_excludes(rootpath, excludes)
                recurse_tree(rootpath, excludes, opts)
            else:
                print '%s is not a valid output destination directory.' % opts.destdir
        else:
            print '%s is not a valid directory.' % rootpath


if __name__ == '__main__':
    main()

