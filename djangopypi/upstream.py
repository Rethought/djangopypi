"""
Utility code for fetching and caching package index data and package files from
upstream repositories.
"""
import logging
import md5
import os
import requests
import socket
import urllib
import xmlrpclib

from django.conf import settings
from django.utils.datastructures import MultiValueDict
from djangopypi.models import (Package,
                               Release,
                               Distribution)

logger = logging.getLogger('cache')


class PyPiCacheError(Exception):
    pass


__PROXY_CACHE__ = {}


def get_upstream(index_url):
    """
    Return an XMLRPC server proxy for the upstream index at ``index_url``.
    Proxy object is cached for convenience and the cached version is
    returned if present.
    """
    if index_url in __PROXY_CACHE__:
        logger.debug("Proxy for {0} returned from cache".format(index_url))
        proxy = __PROXY_CACHE__[index_url]
    else:
        logger.debug("Creating new proxy for {0}".format(index_url))
        proxy = xmlrpclib.ServerProxy(urllib.basejoin(index_url, "pypi/"))
        __PROXY_CACHE__[index_url] = proxy

    return proxy


def find_package_upstream(package, version=''):
    """
    Cycle through upstream indexes as in ``DJANGOPYPI_UPSTREAM_INDEXES``
    until the package sought is found or indexes are exhausted, in which case
    raise ``PyPiCacheError``.

    if ``version`` is ``None`` or empty, the latest version of the package
    is returned from the first upstream that has the package. Note that this
    may NOT be the latest version available if a later upstream in the list
    has a more up to date version than the first upstream which can provide
    the package because the search stops at the first success.
    """
    for upstream in settings.DJANGOPYPI_UPSTREAM_INDEXES:
        logger.debug("Searching for {0}=={1} at {2}"
                     .format(package, version, upstream))
        proxy = get_upstream(upstream)

        try:
            if not version:
                version_list = proxy.package_releases(package)
                if version_list:
                    version = version_list[0]
                else:
                    logger.debug("{0} (any version) not found at {1}"
                                 .format(package, upstream))
                    continue

            urls = proxy.release_urls(package, version)
            urls = {} if not urls else urls[0]
            data = proxy.release_data(package, version)

            if not urls and not data:
                logger.debug("{0}=={1} not found at {2}"
                             .format(package, version, upstream))
                continue


            logger.debug("Found {0}=={1} at {2}"
                         .format(package, version, upstream))

            return dict(urls=urls, data=data, package=package,
                        version=version)
        except socket.gaierror:
            logger.error("Cannot connect to upstream at {0}".format(upstream))

    logger.debug("No upstream package for {0}=={1}".format(package, version))
    raise PyPiCacheError("Could not find package {0}=={1} upstream"
                         .format(package, version))


def download_package_file(metadata, target_dir):
    """
    Given metadata as returned from ``find_package_upstream``, download
    package file and put into ``target_dir``.

    MD5 hash is checked and an exception raised if it does not match
    the metadata entry.

    There are delinquent cases where the call to get 'urls', which returns
    the download path and md5 hash amongst other things in most cases,
    but occasionally returns nothing (example being python-memcached version
    1.48). This function will fallback to trying the ``download_url`` in
    the ``data`` dictionary and will skip MD5 checksumming as it will
    not have the checksum to compare against.

    Return fully qualified path to the download.
    """
    if metadata['urls']:
        url = metadata['urls']['url']
        fname = metadata['urls']['filename']
        md5hash = metadata['urls']['md5_digest']
    else:
        url = metadata['data']['download_url']
        if not url.startswith('http'):
            raise PyPiCacheError(
                "Cannot find download URL for {0}-{1}"
                .format(metadata['package'], metadata['version']))
        fname = url.split('/')[-1]
        md5hash = None

    logger.debug("Downloading {0}".format(url))
    cache_path = os.path.join(target_dir, fname)
    download = requests.get(url)

    if md5hash:
        hasher = md5.new()
        hasher.update(download.content)
        download_hash = hasher.hexdigest()
        if download_hash != md5hash:
            msg = "MD5 mismatch on {0}: {1} != {2}".format(fname,
                                                           download_hash, md5hash)
            logger.error(msg)
            raise PyPiCacheError(msg)
        else:
            logger.debug("Good hash from {0}".format(fname))
    else:
        logger.debug("No hash from server with which to compare. "
                     "Hash check skipped")

    f = open(cache_path, 'wb')
    f.write(download.content)
    f.close()
    return cache_path, fname


def _to_mvd(_dict):
    """
    Convert dict to MultiValueDict, where all values are in lists. This
    is a necessity for package_info because the model assumes key/values
    coming in from a HTTP form submission. I'd rather the form made a
    normal dict and passed that through, but until I do that refactor
    I'll use this... (MP)
    """
    d2 = {}
    for k, v in _dict.items():
        d2[k] = [v]
    return MultiValueDict(d2)


def create_index(metadata, fname):
    """
    Create local index entries based on ``metadata`` as supplied from
    ``find_package_upstream``. ``fname`` is the actual name of the file on
    disk in the cache.

    In the event that ``metadata`` has no valid 'urls' component (which can
    happen with certain bad records from PyPi) then the filetype is assumed
    to be a source distribution. This assumption may be risky.
    """
    package = Package.objects.get_or_create(name=metadata['package'])[0]
    package.auto_hide = False
    package.save()
    release = Release.objects.get_or_create(package=package,
                                            version=metadata['version'])[0]
    release.package_info = _to_mvd(metadata['data'])
    release.metadata_version = "1.1"
    release.hidden = False
    release.save()

    dist = Distribution.objects.get_or_create(release=release)[0]
    dist.content.name = os.path.join(settings.DJANGOPYPI_RELEASE_UPLOAD_TO,
                                     fname)
    try:
        dist.filetype = metadata['urls']['packagetype']
    except KeyError:
        dist.filetype = 'sdist'
    dist.save()


def cache_package(package, version=''):
    """
    Seek package of specified version, or the latest if not supplied, and cache

    Download meta data, download the package file, create index entry and
    return.

    Some packages, such as django, need to be referred to ad Django
    (capitalised). pypi.python.org redirects when you go to ``/simple/django``
    but we'll just have a go at capitalizing a package name if we fail to find
    it first time. If it fails again, we ditch and you'll just have to put
    it in the requirements file or in the pip command
    in appropriate capitalization.
    """
    for pkg in [package, package.capitalize()]:
        try:
            upstream_data = find_package_upstream(pkg, version)
            package = upstream_data['package']
            break
        except  PyPiCacheError:
            continue
    else:
        raise PyPiCacheError("Cannot find upstream for {0}".format(package))

    cached_file, fname = download_package_file(
        upstream_data,
        os.path.join(settings.MEDIA_ROOT,
                     settings.DJANGOPYPI_RELEASE_UPLOAD_TO))

    create_index(upstream_data, fname)
    return cached_file
