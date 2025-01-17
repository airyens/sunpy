"""
SunPy: Python for Solar Physics

The SunPy project is an effort to create an open-source software library for
solar physics using the Python programming language.
"""
#pylint: disable=W0404,W0621
import os
import imp
import shutil
from paver.easy import *
from paver.setuputils import setup

# This is not pretty, but necessary
install = imp.load_source(
    'setup', os.path.join(os.path.dirname(__file__), 'setup.py')).install

#
# Options
#
options(
    deploy = Bunch(
        htmldir = path('doc/source/_build/html'),
        host = 'sipwork.org',
        hostpath = 'www/sunpy/doc'
    ),
    sphinx = Bunch(docroot='doc/source', builddir="_build"),
    upload_docs = Bunch(upload_dir='doc/html'),
    pylint = Bunch(quiet=False)
)

#
# Packaging
#

install(setup)

@task
@needs('prepare_docs', 'setuptools.command.sdist')
def sdist():
    """Generated HTML docs and builds a tarball."""
    shutil.rmtree('doc/html')
    
@task
@needs('prepare_docs', 'setuptools.command.bdist_wininst')
def bdist():
    """Generated HTML docs and builds a windows binary."""
    shutil.rmtree('doc/html')

#
# Documentation
#
@task
@needs('paver.doctools.html')
def prepare_docs():
    """Prepares the SunPy HTML documentation for packaging"""
    sourcedir = 'doc/source/_build/html'
    destdir = 'doc/html'
    if os.path.exists(destdir):
        shutil.rmtree(destdir)
    shutil.move(sourcedir, destdir)
    
@task
@needs('paver.doctools.html', 'upload_docs')
@cmdopts([('username=', 'u', 'Username')])
def deploy(options):
    """Update the docs on sunpy.org"""
    if "username" not in options:
        options.username = raw_input("Username: ")
    sh("rsync -avz -e ssh %s/ %s@%s:%s/" % (options.htmldir,
        options.username, options.host, options.hostpath))

#
# PyLint
#
@task
@cmdopts([('quiet', 'q', 'Run PyLint in quiet mode')])
def pylint(options):
    """Checks the code using PyLint"""
    from pylint import lint
    
    arguments = ['--rcfile=tools/pylint/pylintrc']
    
    if options.quiet:
        arguments.extend(["-rn"])
        
    arguments.extend(["sunpy/"])
    lint.Run(arguments)
    
#
# Cleanup
#
@task
@needs('paver.doctools.doc_clean')
def clean():
    """Cleans up build files"""
    from glob import glob
    
    dirs = (['doc/html', 'doc/source/_build', 'build', 'dist', 'sunpy.egg-info'] + 
             glob('doc/source/reference/generated') + 
             glob('doc/source/reference/*/generated'))

    for dir_ in dirs:
        if os.path.exists(dir_):
            shutil.rmtree(dir_)

    for file_ in glob('distribute-*') + ['MANIFEST']:
        if os.path.exists(file_):
            os.remove(file_)
