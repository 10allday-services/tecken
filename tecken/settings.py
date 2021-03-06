# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, you can obtain one at http://mozilla.org/MPL/2.0/.

"""
Django settings for tecken project.
"""

import logging
import subprocess
import os
from urllib.parse import urlparse

from configurations import Configuration, values
from dockerflow.version import get_version
from raven.transport.requests import RequestsHTTPTransport


class AWS:
    "AWS configuration"

    AWS_CONFIG = {
        # AWS EC2 configuration
        # 'AWS_REGION': 'us-west-2',
        # 'EC2_KEY_NAME': '20161025-dataops-dev',
    }


class Celery:

    # Add a 5 minute soft timeout to all Celery tasks.
    CELERY_TASK_SOFT_TIME_LIMIT = 60 * 5

    # And a 10 minute hard timeout.
    CELERY_TASK_TIME_LIMIT = CELERY_TASK_SOFT_TIME_LIMIT * 2


class S3:

    # How many max seconds to wait for a S3 connection when
    # doing a lookup.
    S3_LOOKUP_CONNECT_TIMEOUT = values.IntegerValue(2)  # seconds
    S3_LOOKUP_READ_TIMEOUT = values.IntegerValue(4)  # seconds

    # The timeouts for doing S3 uploads.
    # When testing S3 PUT in Stage, the longest PUTs take 20 seconds.
    S3_PUT_CONNECT_TIMEOUT = values.IntegerValue(10)  # seconds
    # If upload takes longer than this it's probably best to back off.
    # The client will likely get a 504 error and will retry soon again.
    S3_PUT_READ_TIMEOUT = values.IntegerValue(30)  # seconds


class Core(AWS, Celery, S3, Configuration):
    """Settings that will never change per-environment."""

    # Build paths inside the project like this: os.path.join(BASE_DIR, ...)
    THIS_DIR = os.path.dirname(os.path.abspath(__file__))
    BASE_DIR = os.path.dirname(THIS_DIR)

    VERSION = get_version(BASE_DIR)

    # Using the default first site found by django.contrib.sites
    SITE_ID = 1

    INSTALLED_APPS = [
        "whitenoise.runserver_nostatic",
        # Django apps
        "django.contrib.sites",
        "django.contrib.auth",
        "django.contrib.contenttypes",
        "django.contrib.sessions",
        # Project specific apps
        "tecken.apps.TeckenAppConfig",
        "tecken.symbolicate",
        "tecken.download",
        "tecken.upload",
        "tecken.tokens",
        "tecken.api",
        "tecken.useradmin",
        "tecken.benchmarking",
        # Third party apps
        "dockerflow.django",
        # Third party apps, that need to be listed last
        "mozilla_django_oidc",
    ]

    # June 2017: Notice that we're NOT adding
    # 'mozilla_django_oidc.middleware.RefreshIDToken'. That's because
    # most views in this project are expected to be called as AJAX
    # or from curl. So it doesn't make sense to require every request
    # to refresh the ID token.
    # Once there is a way to do OIDC ID token refreshing without needing
    # the client to redirect, we can enable that.
    # Note also, the ostensible reason for using 'RefreshIDToken' is
    # to check that a once-authenticated user is still a valid user.
    # So if that's "disabled", that's why we have rather short session
    # cookie age.
    MIDDLEWARE = (
        "dockerflow.django.middleware.DockerflowMiddleware",
        # 'django.middleware.csrf.CsrfViewMiddleware',
        "django.contrib.sessions.middleware.SessionMiddleware",
        "django.middleware.common.CommonMiddleware",
        "django.contrib.auth.middleware.AuthenticationMiddleware",
        "tecken.tokens.middleware.APITokenAuthenticationMiddleware",
        # Important that this comes after APITokenAuthenticationMiddleware
        "tecken.useradmin.middleware.NotBlockedInAuth0Middleware",
        "whitenoise.middleware.WhiteNoiseMiddleware",
    )

    ROOT_URLCONF = "tecken.urls"

    WSGI_APPLICATION = "tecken.wsgi.application"

    # Add the django-allauth authentication backend.
    AUTHENTICATION_BACKENDS = (
        "django.contrib.auth.backends.ModelBackend",
        "mozilla_django_oidc.auth.OIDCAuthenticationBackend",
    )

    # Internationalization
    # https://docs.djangoproject.com/en/1.9/topics/i18n/
    LANGUAGE_CODE = "en-us"
    TIME_ZONE = "UTC"
    USE_I18N = False
    USE_L10N = False
    USE_TZ = True
    DATETIME_FORMAT = "Y-m-d H:i"  # simplified ISO format since we assume UTC

    STATIC_ROOT = values.Value(default=os.path.join(BASE_DIR, "frontend/build"))

    STATIC_URL = "/"

    # The default Cache-Control max-age used,
    WHITENOISE_MAX_AGE = values.IntegerValue(60 * 60)
    WHITENOISE_ALLOW_ALL_ORIGINS = False

    SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
    SESSION_CACHE_ALIAS = "default"

    # System Checks
    # Override certain builtin Django system checks because we know
    # with confidence we do these good deeds in Nginx.
    # https://docs.djangoproject.com/en/1.11/ref/checks/#security
    SILENCED_SYSTEM_CHECKS = [
        "security.W001",  # Dealt with using Nginx headers
        "security.W002",  # Dealt with using Nginx headers
        "security.W003",  # CSRF is explicit only on the views that need it
        # We can't set SECURE_HSTS_INCLUDE_SUBDOMAINS since this runs under a
        # mozilla.org subdomain
        "security.W005",
        "security.W004",  # Strict-Transport-Security is set in Nginx
    ]

    OIDC_RP_CLIENT_ID = values.SecretValue()
    OIDC_RP_CLIENT_SECRET = values.SecretValue()

    OIDC_OP_AUTHORIZATION_ENDPOINT = values.URLValue(
        "https://auth.mozilla.auth0.com/authorize"
    )
    OIDC_OP_TOKEN_ENDPOINT = values.URLValue(
        "https://auth.mozilla.auth0.com/oauth/token"
    )
    OIDC_OP_USER_ENDPOINT = values.URLValue("https://auth.mozilla.auth0.com/userinfo")

    # Feature flag for the Auth0 Management API check that checks if users
    # are still valid and not blocked in Auth0's user database.
    ENABLE_AUTH0_BLOCKED_CHECK = values.BooleanValue(True)

    # There's a middleware that checks if the user is NOT blocked in
    # Auth0. But we don't want to do it for every single request, since
    # it's slowish, so we throttle that check with a cache interval.
    NOT_BLOCKED_IN_AUTH0_INTERVAL_SECONDS = values.IntegerValue(60 * 60 * 24)

    # Keep it quite short because we don't have a practical way to do
    # OIDC ID token renewal for this AJAX and curl heavy app.
    SESSION_COOKIE_AGE = values.IntegerValue(60 * 60 * 24 * 365)

    # Where users get redirected after successfully signing in
    LOGIN_REDIRECT_URL = "/?signedin=true"
    LOGIN_REDIRECT_URL_FAILURE = "/?signin=failed"

    # API Token authentication is off by default until Tecken has
    # gone through a security checklist.
    ENABLE_TOKENS_AUTHENTICATION = values.BooleanValue(True)

    TOKENS_DEFAULT_EXPIRATION_DAYS = values.IntegerValue(365)  # 1 year

    # When a symbol is tried to be downloaded, and it turns out the symbol
    # does *not* exist in S3, we write this down so all missing symbols
    # can be post-processed after.
    # But we only need to write it down once per symbol. There's a memoizing
    # guard and this defines how long it should cache that it memoized.
    MEMOIZE_LOG_MISSING_SYMBOLS_SECONDS = values.IntegerValue(60 * 60 * 24)

    # Whether or not benchmarking is enabled. It's only useful to have this
    # enabled in environments dedicated for testing and load testing.
    BENCHMARKING_ENABLED = values.BooleanValue(False)

    # When we ask S3 for the size (if it exists) of a symbol already in S3
    # this can be cached. This value determines how long we do that caching.
    MEMOIZE_KEY_EXISTING_SIZE_SECONDS = values.IntegerValue(60 * 60 * 24)

    # When we upload a .zip file, we iterate over the content and for each
    # file within (that isn't immediately "ignorable") we kick off a
    # function which figures out what (and how) to process the file.
    # That function involves doing a S3 GET (technically ListObjectsV2),
    # (possible) gzipping the payload and (possibly) a S3 PUT.
    # All of these function calls get put in a
    # concurrent.futures.ThreadPoolExecutor pool. This setting is about
    # how many of these to start, max.
    UPLOAD_FILE_UPLOAD_MAX_WORKERS = values.IntegerValue(default=None)

    # Whether to store the missing symbols in Postgres or not.
    # If you disable this, at the time of writing, missing symbols
    # will be stored in the Redis default cache.
    ENABLE_STORE_MISSING_SYMBOLS = values.BooleanValue(True)

    # The prefix used when generating directories in the temp directory.
    UPLOAD_TEMPDIR_PREFIX = values.Value("raw-uploads")

    # When doing local development, especially load testing, it's sometimes
    # useful to be able to bypass all URL checks for Upload by Download.
    ALLOW_UPLOAD_BY_ANY_DOMAIN = values.BooleanValue(False)

    # This is only really meant for the sake of being overrideable by
    # other setting classes; in particular the 'Test' class.
    SYNCHRONOUS_UPLOAD_FILE_UPLOAD = False

    DOWNLOAD_LEGACY_PRODUCTS_PREFIXES = [
        "firefox",
        "seamonkey",
        "sunbird",
        "thunderbird",
        "xulrunner",
        "fennec",
        "b2g",
    ]


class Base(Core):
    """Settings that may change per-environment, some with defaults."""

    @classmethod
    def setup(cls):
        super(Base, cls).setup()

        # For the sake of convenience we want to make UPLOAD_TRY_SYMBOLS_URL
        # optional as an environment variable. If it's not set, set it
        # by taking the UPLOAD_DEFAULT_URL and adding the prefix "/try"
        # right after the bucket name.
        if not cls.UPLOAD_TRY_SYMBOLS_URL:
            default_url = urlparse(cls.UPLOAD_DEFAULT_URL)
            path = default_url.path.split("/")
            # Since it always start with '/', the point after the bucket
            # name is the 3rd one.
            path.insert(2, "try")
            # Note `._replace` is actually not a private method.
            try_url = default_url._replace(path="/".join(path))
            cls.UPLOAD_TRY_SYMBOLS_URL = try_url.geturl()

    SECRET_KEY = values.SecretValue()

    DEBUG = values.BooleanValue(default=False)
    DEBUG_PROPAGATE_EXCEPTIONS = values.BooleanValue(default=False)

    ALLOWED_HOSTS = values.ListValue([])

    DATABASES = values.DatabaseURLValue("postgres://postgres:postgres@db/tecken")
    CONN_MAX_AGE = values.IntegerValue(60)

    REDIS_URL = values.Value("redis://redis-cache:6379/0")
    REDIS_STORE_URL = values.Value("redis://redis-store:6379/0")

    REDIS_SOCKET_CONNECT_TIMEOUT = values.IntegerValue(1)
    REDIS_SOCKET_TIMEOUT = values.IntegerValue(2)
    REDIS_STORE_SOCKET_CONNECT_TIMEOUT = values.IntegerValue(1)
    REDIS_STORE_SOCKET_TIMEOUT = values.IntegerValue(2)

    # Use redis as the Celery broker.
    @property
    def CELERY_BROKER_URL(self):
        return self.REDIS_URL

    # This name is hardcoded inside django-redis. It it's set to true in `settings`
    # it means that django-redis will attempt WARNING log any exceptions that
    # happen with the connection when it swallows the error(s).
    DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS = values.BooleanValue(True)

    REDIS_IGNORE_EXCEPTIONS = values.BooleanValue(True)

    @property
    def CACHES(self):
        return {
            "default": {
                "BACKEND": "django_redis.cache.RedisCache",
                "LOCATION": self.REDIS_URL,
                "OPTIONS": {
                    "COMPRESSOR": "django_redis.compressors.zlib.ZlibCompressor",  # noqa
                    # "SERIALIZER": "django_redis.serializers.msgpack.MSGPackSerializer",  # noqa
                    "SERIALIZER": "tecken.cache_extra.MSGPackSerializer",  # noqa
                    "SOCKET_CONNECT_TIMEOUT": self.REDIS_SOCKET_CONNECT_TIMEOUT,
                    "SOCKET_TIMEOUT": self.REDIS_SOCKET_TIMEOUT,
                    "IGNORE_EXCEPTIONS": self.REDIS_IGNORE_EXCEPTIONS,
                },
            },
            "store": {
                "BACKEND": "django_redis.cache.RedisCache",
                "LOCATION": self.REDIS_STORE_URL,
                "OPTIONS": {
                    "COMPRESSOR": "django_redis.compressors.zlib.ZlibCompressor",  # noqa
                    "SERIALIZER": "tecken.cache_extra.MSGPackSerializer",  # noqa
                    "SOCKET_CONNECT_TIMEOUT": self.REDIS_STORE_SOCKET_CONNECT_TIMEOUT,
                    "SOCKET_TIMEOUT": self.REDIS_STORE_SOCKET_TIMEOUT,
                },
            },
        }

    LOGGING_USE_JSON = values.BooleanValue(False)

    LOGGING_DEFAULT_LEVEL = values.Value("INFO")

    def LOGGING(self):
        config = {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "json": {
                    "()": "dockerflow.logging.JsonLogFormatter",
                    "logger_name": "tecken",
                },
                "verbose": {"format": "%(levelname)s %(asctime)s %(name)s %(message)s"},
            },
            "handlers": {
                "console": {
                    "level": self.LOGGING_DEFAULT_LEVEL,
                    "class": "logging.StreamHandler",
                    "formatter": ("json" if self.LOGGING_USE_JSON else "verbose"),
                },
                "sentry": {
                    "level": "ERROR",
                    "class": (
                        "raven.contrib.django.raven_compat.handlers.SentryHandler"
                    ),
                },
                "null": {"class": "logging.NullHandler"},
            },
            "root": {"level": "INFO", "handlers": ["sentry", "console"]},
            "loggers": {
                "django": {
                    "level": "INFO",
                    "handlers": ["console"],
                    "propagate": False,
                },
                "django.db.backends": {
                    "level": "ERROR",
                    "handlers": ["console"],
                    "propagate": False,
                },
                "django.request": {
                    "level": "INFO",
                    "handlers": ["console"],
                    "propagate": False,
                },
                "raven": {
                    "level": "DEBUG",
                    "handlers": ["console"],
                    "propagate": False,
                },
                "sentry.errors": {
                    "level": "DEBUG",
                    "handlers": ["console"],
                    "propagate": False,
                },
                "tecken": {
                    "level": "DEBUG",
                    "handlers": ["console"],
                    "propagate": False,
                },
                "mozilla_django_oidc": {
                    "level": "DEBUG",
                    "handlers": ["console"],
                    "propagate": False,
                },
                "celery.task": {
                    "level": "DEBUG",
                    "handlers": ["console"],
                    "propagate": False,
                },
                "markus": {
                    "level": "INFO",
                    "handlers": ["console"],
                    "propagate": False,
                },
                "request.summary": {
                    "handlers": ["console"],
                    "level": "INFO",
                    "propagate": False,
                },
                "django.security.DisallowedHost": {
                    "handlers": ["null"],
                    "propagate": False,
                },
                "django_redis.cache": {
                    "level": "INFO",
                    "handlers": ["console"],
                    "propagate": False,
                },
            },
        }
        if not self.LOGGING_USE_JSON:
            # If you're not using JSON logging, there's no point using the
            # 'request.summary' logger that python-dockerflow uses.
            config["loggers"]["request.summary"]["handlers"] = []
        return config

    CSRF_FAILURE_VIEW = "tecken.views.csrf_failure"
    CSRF_USE_SESSIONS = values.BooleanValue(True)

    # The order here matters. Symbol download goes through these one at a time.
    # Ideally you want the one most commonly hit first unless there's a
    # cascading reason you want other buckets first.
    # By default, each URL is assumed to be private!
    # If there's a bucket you want to include that should be accessed
    # by HTTP only, add '?access=public' to the URL.
    # Note that it's empty by default which is actually not OK.
    # For production-like environments this must be something or else
    # Django won't start. (See tecken.apps.TeckenAppConfig)
    #
    SYMBOL_URLS = values.ListValue([])

    # Same as with SYMBOL_URLS, this has to be set to something
    # or else Django won't start.
    UPLOAD_DEFAULT_URL = values.Value()

    # When an upload comes in with symbols from a Try build, these symbols
    # mustn't be uploaded with the "regular symbols".
    # This value can be very similar to UPLOAD_DEFAULT_URL in that
    # it can use the exact same S3 bucket but have a different prefix.
    #
    # Note! By default the value for 'UPLOAD_TRY_SYMBOLS_URL' becomes
    # the value of 'UPLOAD_DEFAULT_URL' but with a '/try' suffix added.
    UPLOAD_TRY_SYMBOLS_URL = values.Value()
    # # The reason for this is to simplify things in local dev and non-Prod
    # # environments where the location isn't as important.
    # # Basically, if don't set this, the value
    # # becomes `settings.UPLOAD_DEFAULT_URL + '/try'` (but carefully so)
    # @property
    # def UPLOAD_TRY_SYMBOLS_URL(self):
    #     print(Configuration.LANGUAGES)
    #     print(Configuration.UPLOAD_TRY_SYMBOLS_URL)
    #     # # super()
    #     # print(dir(self))
    #     # print(self.UPLOAD_TRY_SYMBOLS_URL.value.copy())
    #     return '/TRY'
    #     value = super().value
    #     return value + '/TRY'

    # The config is a list of tuples like this:
    # 'email:url' where the email part can be a glob like regex
    # For example '*@example.com:https://s3-us-west-2.amazonaws.com/mybucket'
    # will upload all symbols to a bucket called 'mybucket' for anybody
    # with a @example.com email.

    # This is a config that, typed as a Python dictionary, specifies
    # specific email addresses or patterns to custom URLs.
    # For example '{"peter@example.com": "https://s3.amazonaws.com/mybucket"}'
    # or '{"*@example.com": "https://s3.amazonaws.com/otherbucket"}' for
    # anybody uploading with an @example.com email address.
    UPLOAD_URL_EXCEPTIONS = values.DictValue({})

    # XXX Can this be deleted?
    # When an upload comes in, we need to store it somewhere that it
    # can be shared between the webapp and the Celery worker.
    # In production-like environments this can't be a local filesystem
    # path but needs to one that is shared across servers. E.g. EFS.
    # UPLOAD_INBOX_DIRECTORY = values.Value("./upload-inbox")

    # The default prefix for locating all symbols
    SYMBOL_FILE_PREFIX = values.Value("v1")

    # During upload, for each file in the archive, if the extension
    # matches this list, the file gets gzip compressed before uploading.
    COMPRESS_EXTENSIONS = values.ListValue(["sym"])

    # For specific file uploads, override the mimetype.
    # For .sym files, for example, if S3 knows them as 'text/plain'
    # they become really handy to open in a browser and view directly.
    MIME_OVERRIDES = values.DictValue({"sym": "text/plain"})

    # Number of seconds to wait for a symbol download. If this
    # trips, no error will be raised and we'll just skip using it
    # as a known symbol file.
    # The value gets cached as an empty dict for one hour.
    SYMBOLS_GET_TIMEOUT = values.Value(5)

    # Individual strings that can't be allowed in any of the lines in the
    # content of a symbols archive file.
    DISALLOWED_SYMBOLS_SNIPPETS = values.ListValue(
        [
            # https://bugzilla.mozilla.org/show_bug.cgi?id=1012672
            "qcom/proprietary"
        ]
    )

    DOCKERFLOW_CHECKS = [
        "dockerflow.django.checks.check_database_connected",
        "dockerflow.django.checks.check_migrations_applied",
        "dockerflow.django.checks.check_redis_connected",
        "tecken.dockerflow_extra.check_redis_store_connected",
        "tecken.dockerflow_extra.check_storage_urls",
    ]

    # We can cache quite aggressively here because the SymbolDownloader
    # has chance to invalidate certain keys.
    # Also, any time a symbol archive file is upload, for each file within
    # that we end up uploading to S3 we also cache invalidate.
    SYMBOLDOWNLOAD_EXISTS_TTL_SECONDS = values.IntegerValue(60 * 60 * 6)

    # How many uploads to display per page when paginating through
    # past uploads.
    API_UPLOADS_BATCH_SIZE = 20
    API_UPLOADS_CREATED_BATCH_SIZE = 20
    API_FILES_BATCH_SIZE = 40
    API_DOWNLOADS_MISSING_BATCH_SIZE = 20

    # Every time we do a symbol upload, we also take a look to see if there
    # are incomplete uploads that could have failed due to some unlucky
    # temporary glitch.
    # When we do the reattempt, we need to wait sufficiently long because
    # the upload might just be incomplete because it's in the queue, not
    # because it failed.
    # Note also, if the job is put back into a celery job, we also log
    # this in the cache so that it doesn't add it more than once. That
    # caching uses this same timeout.
    UPLOAD_REATTEMPT_LIMIT_SECONDS = values.IntegerValue(60 * 60 * 12)

    # When you "upload by download", the URL's domain needs to be in this
    # allow list. This is to double-check that we don't allow downloads from
    # domains we don't fully trust.
    ALLOW_UPLOAD_BY_DOWNLOAD_DOMAINS = values.ListValue(
        [
            "queue.taskcluster.net",
            "firefox-ci-tc.services.mozilla.com",
            "stage.taskcluster.nonprod.cloudops.mozgcp.net",
        ]
    )

    # A list of file extensions that if a file is NOT one of these extensions
    # we can immediately return 404 and not bother to process for anything
    # else.
    # It's case sensitive and has to be lower case.
    # As a way to get marginal optimization of this, make sure '.sym' is
    # first in the list since it's the most common.
    DOWNLOAD_FILE_EXTENSIONS_ALLOWED = values.ListValue(
        [".sym", ".dl_", ".ex_", ".pd_", ".dbg.gz", ".tar.bz2"]
    )


class Localdev(Base):
    """Configuration to be used during local development and base class
    for testing"""

    # Override some useful developer settings to be True by default.
    ENABLE_TOKENS_AUTHENTICATION = values.BooleanValue(True)
    DEBUG = values.BooleanValue(default=True)
    DEBUG_PROPAGATE_EXCEPTIONS = values.BooleanValue(default=True)

    # When doing localdev, these defaults will suffice. The minio
    # one forces you to use/test boto3 and the old public symbols URL
    # forces you to use/test the symbol downloader based on requests.get().
    SYMBOL_URLS = values.ListValue(["http://minio:9000/testbucket"])

    # By default, upload all symbols to this when in local dev.
    UPLOAD_DEFAULT_URL = values.Value("http://minio:9000/testbucket")

    # Note! By default the value for 'UPLOAD_TRY_SYMBOLS_URL' becomes
    # the value of 'UPLOAD_DEFAULT_URL' but with a '/try' prefix added.

    # Run this much sooner in local development.
    UPLOAD_REATTEMPT_LIMIT_SECONDS = values.IntegerValue(60)

    @classmethod
    def post_setup(cls):
        super().post_setup()
        # in case we don't find these AWS config variables in the environment
        # we load them from the .env file
        for param in ("ACCESS_KEY_ID", "SECRET_ACCESS_KEY", "DEFAULT_REGION"):
            if param not in os.environ:
                os.environ[param] = values.Value(
                    default="", environ_name=param, environ_prefix="AWS"
                )

    @property
    def VERSION(self):
        # this was breaking in ci
        return {}
        output = subprocess.check_output(
            # Use the absolute path of 'git' here to avoid 'git'
            # not being the git we expect in Docker.
            ["/usr/bin/git", "describe", "--tags", "--always", "--abbrev=0"]
        )  # nosec
        if output:
            return {"version": output.decode().strip()}
        else:
            return {}

    MARKUS_BACKENDS = [
        # Commented out, but uncomment if you want to see all the
        # metrics sent to markus.
        # {
        #     'class': 'markus.backends.logging.LoggingMetrics',
        # },
        {
            "class": "markus.backends.datadog.DatadogMetrics",
            "options": {
                "statsd_host": "statsd",
                "statsd_port": 8125,
                "statsd_namespace": "",
            },
        },
        # {"class": "tecken.markus_extra.LogAllMetricsKeys"},
        # {
        #     'class': 'markus.backends.logging.LoggingRollupMetrics',
        #     'options': {
        #         'logger_name': 'markus',
        #         'leader': 'ROLLUP',
        #         'flush_interval': 60
        #     }
        # },
    ]

    # Set these to smaller numbers for the sake of more easily testing
    # pagination in local development.
    API_UPLOADS_BATCH_SIZE = 10
    API_FILES_BATCH_SIZE = 20

    #
    # Default to the test oidcprovider container for Open ID Connect
    #
    # Client ID and secret must match oidcprovider database
    OIDC_RP_CLIENT_ID = values.IntegerValue(1)
    OIDC_RP_CLIENT_SECRET = values.Value("bd01adf93cfb")
    # Load oidcprovider on public port 8081, without /etc/hosts changes
    OIDC_OP_AUTHORIZATION_ENDPOINT = values.URLValue(
        "http://oidc.127.0.0.1.nip.io:8081/openid/authorize"
    )
    # The backend connects to oidcprovider on docker port 8080
    # Django's URL validator, used in URLValue, doesn't like docker hostnames
    OIDC_OP_TOKEN_ENDPOINT = values.Value("http://oidcprovider:8080/openid/token")
    # Same as token switch from URLValue to Value
    OIDC_OP_USER_ENDPOINT = values.Value("http://oidcprovider:8080/openid/userinfo")
    # Allow non-SSL connection to oidcprovider
    OIDC_VERIFY_SSL = values.BooleanValue(False)
    # Disable NotBlockedInAuth0Middleware
    ENABLE_AUTH0_BLOCKED_CHECK = values.BooleanValue(False)


class Test(Localdev):
    """Configuration to be used during testing"""

    DEBUG = False

    # Like Celery's old ALWAYS_EAGER option, this tells the code to
    # swap the ThreadPoolExecutor in for an executor that is
    # entirely synchronous.
    SYNCHRONOUS_UPLOAD_FILE_UPLOAD = True

    # We might not enable it in certain environments but we definitely
    # want to test the code we have.
    ENABLE_TOKENS_AUTHENTICATION = True

    # This feature flag is always off when testing except the tests
    # that enable it deliberately.
    ENABLE_STORE_MISSING_SYMBOLS = False

    # Disable the Auth0 in all tests. THere are some specific tests
    # that switch it back on to test the Auth0 blocked middleware.
    ENABLE_AUTH0_BLOCKED_CHECK = False

    SECRET_KEY = values.Value("not-so-secret-after-all")
    SESSION_COOKIE_SECURE = True

    OIDC_RP_CLIENT_ID = values.Value("not-so-secret-after-all")
    OIDC_RP_CLIENT_SECRET = values.Value("not-so-secret-after-all")

    # nosec
    # Only used for testing to log users in during unit tests
    PASSWORD_HASHERS = ("django.contrib.auth.hashers.MD5PasswordHasher",)

    SYMBOL_URLS = [
        "https://s3.example.com/public/prefix/?access=public",
        "https://s3.example.com/private/prefix/",
    ]

    AUTHENTICATION_BACKENDS = ("django.contrib.auth.backends.ModelBackend",)

    # This makes sure this is never a real valid URL.
    OIDC_OP_USER_ENDPOINT = "https://auth.example.com/authorize"

    SYMBOL_FILE_PREFIX = "v0"
    UPLOAD_DEFAULT_URL = "https://s3.example.com/private/prefix/"
    UPLOAD_TRY_SYMBOLS_URL = "https://s3.example.com/try/prefix"
    UPLOAD_URL_EXCEPTIONS = {"*@peterbe.com": "https://s3.example.com/peterbe-com"}

    @property
    def CACHES(self):
        parent = super(Test, self).CACHES
        parent["default"] = {
            "BACKEND": "tecken.cache_extra.RedisLocMemCache",
            "LOCATION": "unique-snowflake",
        }
        return parent

    MARKUS_BACKENDS = [
        {
            "class": "markus.backends.datadog.DatadogMetrics",
            "options": {
                "statsd_host": "statsd",
                "statsd_port": 8125,
                "statsd_namespace": "",
            },
        },
        # {
        #     'class': 'tecken.markus_extra.LogAllMetricsKeys',
        # },
    ]


class Dev(Base):
    """Configuration to be used in dev server environment"""

    LOGGING_USE_JSON = True

    ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https"
    SECURE_SSL_REDIRECT = True
    # Mark session and CSRF cookies as being HTTPS-only.
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    # This is needed to get a CRSF token in /admin
    ANON_ALWAYS = True

    @property
    def DATABASES(self):
        "require encrypted connections to Postgres"
        DATABASES = super().DATABASES.value.copy()
        DATABASES["default"].setdefault("OPTIONS", {})["sslmode"] = "require"
        return DATABASES

    # Sentry setup
    SENTRY_DSN = values.Value(environ_prefix=None)

    MIDDLEWARE = (
        "raven.contrib.django.raven_compat.middleware"
        ".SentryResponseErrorIdMiddleware",
    ) + Base.MIDDLEWARE

    INSTALLED_APPS = Base.INSTALLED_APPS + ["raven.contrib.django.raven_compat"]

    SENTRY_CELERY_LOGLEVEL = logging.INFO

    @property
    def RAVEN_CONFIG(self):
        config = {"dsn": self.SENTRY_DSN, "transport": RequestsHTTPTransport}
        if self.VERSION:
            config["release"] = (
                self.VERSION.get("version") or self.VERSION.get("commit") or ""
            )
        return config

    # Defaulting to 'localhost' here because that's where the Datadog
    # agent is expected to run in production.
    STATSD_HOST = values.Value("localhost")
    STATSD_PORT = values.Value(8125)
    STATSD_NAMESPACE = values.Value("")

    @property
    def MARKUS_BACKENDS(self):
        return [
            {
                "class": "markus.backends.datadog.DatadogMetrics",
                "options": {
                    "statsd_host": self.STATSD_HOST,
                    "statsd_port": self.STATSD_PORT,
                    "statsd_namespace": self.STATSD_NAMESPACE,
                },
            }
        ]


class Stage(Dev):
    """Configuration to be used in stage environment"""


class Prod(Stage):
    """Configuration to be used in prod environment"""


class Prodlike(Prod):
    """Configuration when you want to run, as if it's in production, but
    in docker."""

    DEBUG = False

    SYMBOL_URLS = Localdev.SYMBOL_URLS
    UPLOAD_DEFAULT_URL = Localdev.UPLOAD_DEFAULT_URL

    # Make it possible to disable this in local prod-like environments
    # but still make it True by default
    LOGGING_USE_JSON = values.BooleanValue(True)

    @property
    def DATABASES(self):
        "Don't require encrypted connections to Postgres"
        DATABASES = super().DATABASES.copy()
        DATABASES["default"].setdefault("OPTIONS", {})["sslmode"] = "disable"
        return DATABASES

    MARKUS_BACKENDS = []

    # If you try to run with prod like settings locally, you most likely
    # have to use a self-signed SSL cert.
    SECURE_HSTS_SECONDS = 60

    if os.environ.get("DJANGO_RUN_INSECURELY", False):  # hackish, but works
        # When running with DJANGO_CONFIGURATION=Prodlike, if you don't want
        # to have to use HTTPS, uncomment these lines:
        ACCOUNT_DEFAULT_HTTP_PROTOCOL = "http"
        SECURE_SSL_REDIRECT = False
        SECURE_HSTS_SECONDS = 0
        SECURE_HSTS_PRELOAD = False


class Build(Prod):
    """Configuration to be used in build (!) environment"""

    SECRET_KEY = values.Value("not-so-secret-after-all")
