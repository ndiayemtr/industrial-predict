"""Explicit browser profile and projection of the existing authorization policy.

No engine, discovery, admission, new permission policy or default activation.
The qualification guard is a trusted server integration, never client input.
"""
from dataclasses import dataclass
import ipaddress
import logging
import re
from typing import Callable
from urllib.parse import urlsplit

from app.core.authorization import AuthorizationEffect, MembershipState, Permission, decide_authorization
from app.core.caller_session import CurrentCaller, CallerForbidden, CallerProviderUnavailable
from app.core.database_runtime import SqlRuntime

BROWSER_BRIDGE = 'industrial-predict:b2b-session:v1'
AUTH_PATHS = frozenset(('/auth/oidc/google/start', '/auth/oidc/google/callback',
                       '/api/v1/auth/me', '/api/v1/auth/logout'))
DIAGNOSTIC_PATHS = frozenset(('/health', '/__dev/identity', '/docs', '/docs/oauth2-redirect',
                            '/redoc', '/openapi.json'))


def https_origin(value):
    """Canonical browser origin: no credentials, path, query, wildcard or 443 alias."""
    try:
        if type(value) is not str or not value.isascii() or any(ord(c) < 33 or ord(c) == 127 for c in value):
            raise ValueError()
        p = urlsplit(value)
        if p.scheme != 'https' or not p.hostname or p.username is not None or p.password is not None or p.path or p.query or p.fragment:
            raise ValueError()
        host = p.hostname
        try:
            address = ipaddress.ip_address(host)
            host = '[' + address.compressed + ']' if address.version == 6 else str(address)
        except ValueError:
            if not re.fullmatch(r'[a-z0-9]+(?:[.-][a-z0-9]+)*', host):
                raise ValueError()
        port = p.port
        if port is not None and not 1 <= port <= 65535:
            raise ValueError()
        canonical = 'https://' + host + (':' + str(port) if port is not None and port != 443 else '')
        if canonical != value:
            raise ValueError()
        return canonical
    except (ValueError, TypeError, AttributeError):
        raise ValueError('B2B_BROWSER_HTTPS_ORIGIN_REQUIRED') from None


@dataclass(frozen=True, slots=True, repr=False)
class BrowserAuthProfile:
    origin: str
    qualification_guard: Callable[[SqlRuntime], None]

    def __post_init__(self):
        https_origin(self.origin)
        if not callable(self.qualification_guard):
            raise ValueError('B2B_BROWSER_QUALIFICATION_GUARD_REQUIRED')

    def check(self, sql):
        """Existing destination/TLS/revision/ACL qualification must succeed.

        A typed profile or callback is not proof by itself. The deployment must
        bind the real approved guard; a boolean/readiness/config label is not it.
        """
        try:
            self.__post_init__()
            if (type(sql) is not SqlRuntime or sql.engine.echo or not sql.engine.hide_parameters
                    or sql.engine.logger.isEnabledFor(logging.DEBUG)
                    or self.qualification_guard(sql) is not None):
                raise ValueError()
            return
        except Exception:
            pass
        raise CallerProviderUnavailable() from None


def browser_profile(caller):
    """Only fresh server CurrentCaller data; no domain, role-derived grants or PII."""
    try:
        if type(caller) is not CurrentCaller:
            raise ValueError()
        caller.__post_init__()
        companies = []
        for member in sorted(caller.memberships, key=lambda item: item.company_id):
            if member.state is not MembershipState.ACTIVE:
                continue
            permissions = sorted(p.value for p in Permission if decide_authorization(
                identity=caller.identity, memberships=caller.memberships, company_id=member.company_id,
                permission=p).effect is AuthorizationEffect.ALLOW)
            if permissions:
                companies.append({'companyId': member.company_id, 'displayName': None, 'permissions': permissions})
    except Exception:
        raise CallerProviderUnavailable() from None
    if not companies:
        raise CallerForbidden()
    return {'userId': caller.identity.user_id, 'displayName': None, 'companies': companies}
