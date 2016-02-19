from django.conf import settings
from django.contrib.sites.models import Site
from django.core.cache import cache

from .utils import make_tls_property


_default_site_id = getattr(settings, 'SITE_ID', None)
SITE_ID = settings.__class__.SITE_ID = make_tls_property()


def _get_site(domain):
    """
    First try to look up the site by domain. If that fails, try
    searching for the site's domain minus any ignorable prefixes or
    suffixes, like www. or .local, as set in
    settings.IGNORABLE_SITE_PREFIXES and IGNORABLE_SITE_SUFFIXES. Return
    None if nothing is found.
    """
    try:
        return Site.objects.get(domain=domain)
    except Site.DoesNotExist:
        pass

    ignorable_site_prefixes = getattr(settings, 'IGNORABLE_SITE_PREFIXES', [
        'www.',
    ])

    for prefix in ignorable_site_prefixes:
        if domain.startswith(prefix):
            try:
                return Site.objects.get(domain=domain[len(prefix):])
            except Site.DoesNotExist:
                pass

    ignorable_site_suffixes = getattr(settings, 'IGNORABLE_SITE_SUFFIXES', [
        '.local',
    ])

    for suffix in ignorable_site_suffixes:
        if domain.endswith(suffix):
            try:
                return Site.objects.get(domain=domain[:-len(suffix)])
            except Site.DoesNotExist:
                pass


class DynamicSiteIDMiddleware(object):
    """Sets settings.SITE_ID based on request's domain."""

    def process_request(self, request):
        # Ignore port if it's 80 or 443
        if ':' in request.get_host():
            domain, port = request.get_host().split(':', 1)
        else:
            domain = request.get_host()

        # Domains are case insensitive
        domain = domain.lower()

        # We cache the SITE_ID
        cache_key = 'Site:domain:%s' % domain
        site = cache.get(cache_key)
        if site:
            SITE_ID.value = site
        else:
            site = _get_site(domain)

            # Add site if it doesn't exist
            if not site and getattr(settings, 'CREATE_SITES_AUTOMATICALLY',
                                    True):
                site = Site(domain=domain, name=domain)
                site.save()

            # Set SITE_ID for this thread/request
            if site:
                SITE_ID.value = site.pk
            else:
                SITE_ID.value = _default_site_id

            cache.set(cache_key, SITE_ID.value, 5 * 60)
