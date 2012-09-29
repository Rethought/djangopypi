DjangoPyPI
==========

DjangoPyPI is a Django application that provides a re-implementation of the 
`Python Package Index <http://pypi.python.org>`_.  

Installation
------------

Path
____

The first step is to get ``djangopypi`` into your Python path.

Buildout
++++++++

Simply add ``djangopypi`` to your list of ``eggs`` and run buildout again it 
should downloaded and installed properly.

EasyInstall/Setuptools
++++++++++++++++++++++

If you have setuptools installed, you can use ``easy_install djangopypi``

Manual
++++++

Download and unpack the source then run::

    $ python setup.py install

Django Settings
_______________

Add ``djangopypi`` to your ``INSTALLED_APPS`` setting and run ``syncdb`` again 
to get the database tables [#]_.

Then add an include in your url config for ``djangopypi.urls``::

    urlpatterns = patterns("",
        ...
        url(r'', include("djangopypi.urls"))
    )

This will make the repository interface be accessible at ``/pypi/``.


Package upload directory
++++++++++++++++++++++++

By default packages are uploaded to ``<MEDIA_ROOT>/dists`` so you need both
to ensure that ``MEDIA_ROOT`` is assigned a value and that the
``<MEDIA_ROOT>/dists`` directory is created and writable by the web server.

You may change the directory to which packages are uploaded by setting
``DJANGOPYPI_RELEASE_UPLOAD_TO``; this will be a sub-directory of ``MEDIA_ROOT``.


Other settings
++++++++++++++

Look in the ``djangopypi`` source code for ``settings.py`` to see other
settings you can override.


Data initialisation
+++++++++++++++++++

Load the classifier database with the management command::

 $ python manage.py loadclassifiers


Package download handler
++++++++++++++++++++++++

Packages are downloaded from the following URL:
``<host>/simple/<package>/dists/<package>-<version>.tar.gz#<md5 hash>``

You will need to configure either your development server to deliver the
package from the upload directory, or your web server (e.g. NGINX or Apache).

To configure your Django development server ensure that ``urls.py`` looks
something like following::

 import os
 from django.conf.urls import patterns, include, url
 from django.conf import settings

 # ... other code here including Django admin auto-discover ...

 urlpatterns = patterns('',
     # ... url patterns...

     url(r'^simple/[\w\d_\.\-]+/dists/(?P<path>.*)$', 'django.views.static.serve',
             {'document_root': os.path.join(settings.MEDIA_ROOT,
                                            settings.DJANGOPYPI_RELEASE_UPLOAD_TO)}),
     url(r'', include("djangopypi.urls")),

     # .. url patterns...
 )

This should only be used for the Django development server.

When using a web server, configure that to deliver packages from the
upload dist directory directly from this URL. For example, you may have
a clause in an NGINX configuration file something like the following::

 server {
   ... configuration...
   
   location ~ ^/simple/[a-zA-Z0-9\,\-\.]+/dists/ {
       alias /path/to/upload/dists/;
   }

   ... configuration...
 }

Uploading to your PyPI
----------------------

Assuming you are running your Django site locally for now, add the following to 
your ``~/.pypirc`` file::

    [distutils]
    index-servers =
        pypi
        local

    [pypi]
    username:user
    password:secret

    [local]
    username:user
    password:secret
    repository:http://localhost:8000/pypi/

Uploading a package: Python >=2.6
_________________________________

To push the package to the local pypi::

    $ python setup.py register -r local sdist upload -r local


Uploading a package: Python <2.6
________________________________

If you don't have Python 2.6 please run the command below to install the 
backport of the extension for multiple repositories::

     $ easy_install -U collective.dist

Instead of using register and dist command, you can use ``mregister`` and 
``mupload`` which are a backport of python 2.6 register and upload commands 
that supports multiple servers.

To push the package to the local pypi::

    $ python setup.py mregister -r local sdist mupload -r local

.. [#] ``djangopypi`` is South enabled, if you are using South then you will need
   to run the South ``migrate`` command to get the tables.

Installing a package with pip
-----------------------------

To install your package with pip::

 $ pip install -i http://my.pypiserver.com/simple/ <PACKAGE>

If you want to fall back to PyPi or another repository in the event the
package is not on your new server, or in particular if you are installing a number
of packages, some on your private server and some on another, you can use
pip in the following manner::

 $ pip install -i http://my.pypiserver.com/simple/ \
   --extra-index-url=http://pypi.python.org/simple/ \
   -r requirements.txt

(substitute your djangopypi server URL for the ``localhost`` one in this example)

The downside is that each install of a package hosted on the repository in
``--extra-index-url`` will start with a call to the first repository which
will fail before pip falls back to the alternative.

Transparent proxy to an upstream PyPi repository
++++++++++++++++++++++++++++++++++++++++++++++++

The above method works well, but you can also let djangopypi do the hard work
and redirect to an upstream index if the requested package is not found
locally. By default this is disabled. To enable proxying to the default
upstream repository ``http://pypi.python.org`` the following must be set in
``settings.py``::

 DJANGOPYPI_PROXY_MISSING = True

If you'd like to fall-back to some other repository, also add::

 DJANGOPYPI_PROXY_BASE_URL = 'http://my.pypirepository.org'
