import failureflags
import os
import unittest
from unittest.mock import patch, MagicMock

DEFAULT_ENDPOINT = "http://localhost:5032/experiment"

class TestResolveEndpoint(unittest.TestCase):

    def test_defaultWhenNothingIsConfigured(self):
        assert failureflags.resolveEndpoint(None, None, None, None) == DEFAULT_ENDPOINT

    def test_precedence(self):
        explicit = "http://explicit:1/experiment"
        variable = "http://variable:2/experiment"
        assert failureflags.resolveEndpoint(explicit, variable, "host", "3") == explicit
        assert failureflags.resolveEndpoint(None, variable, "host", "3") == variable
        assert failureflags.resolveEndpoint(None, None, "host", "3") == "http://host:3/experiment"

    def test_hostAndPortMayBeSetAlone(self):
        assert failureflags.resolveEndpoint(None, None, "sidecar", None) == "http://sidecar:5032/experiment"
        assert failureflags.resolveEndpoint(None, None, None, "6000") == "http://localhost:6000/experiment"

    def test_blankValuesAreTreatedAsUnset(self):
        assert failureflags.resolveEndpoint("", "  ", "", " ") == DEFAULT_ENDPOINT

    def test_junkPortFallsBackToTheDefault(self):
        # bad configuration must not take the application with it
        for port in ["0", "-1", "70000", "abc", "80.5", ""]:
            assert failureflags.resolveEndpoint(None, None, None, port) == DEFAULT_ENDPOINT, f"port {port!r}"

class TestParsePort(unittest.TestCase):
    """GREMLIN_SIDECAR_PORT is a *listen address* to the sidecar, which requires a colon.
    Parsing it as a plain integer silently discarded every value the sidecar accepts."""

    def test_theFormsTheSidecarAcceptsAllResolveToTheSamePort(self):
        for raw in ["6032", ":6032", "0.0.0.0:6032", "localhost:6032", "127.0.0.1:6032",
                    "[::]:6032", " :6032 ", ":6032 "]:
            with self.subTest(port=raw):
                assert failureflags.parsePort(raw) == 6032, f"port {raw!r}"

    def test_theHostHalfIsIgnored(self):
        # a listen address says what the sidecar binds, not where to reach it, and 0.0.0.0
        # is not a connect target. GREMLIN_SIDECAR_HOST moves the host.
        assert failureflags.resolveEndpoint(None, None, None, "0.0.0.0:6032") == \
            "http://localhost:6032/experiment"
        assert failureflags.resolveEndpoint(None, None, "sidecar", ":6032") == \
            "http://sidecar:6032/experiment"

    def test_junkFallsBackToTheDefault(self):
        for raw in ["", ":", "abc", ":abc", "host:", "0", ":0", "-1", ":-1", "70000",
                    ":70000", "80.5", ":80.5", "6032:6033:", "::"]:
            with self.subTest(port=raw):
                assert failureflags.parsePort(raw) is None, f"port {raw!r}"

    def test_listenAddressFormsReachTheSameEndpointAsABarePort(self):
        bare = failureflags.resolveEndpoint(None, None, None, "6032")
        for raw in [":6032", "0.0.0.0:6032", "localhost:6032"]:
            with self.subTest(port=raw):
                assert failureflags.resolveEndpoint(None, None, None, raw) == bare, \
                    f"port {raw!r} must resolve where a bare port does"

class TestEndpointScheme(unittest.TestCase):

    def test_onlyHttpIsHonoured(self):
        # urlopen would happily honour file:// or ftp://, so a misconfigured endpoint must
        # fall back rather than read a local file and parse it as experiments
        for endpoint in ["file:///etc/passwd", "ftp://host/x", "data:,[]", "gopher://x",
                         "not a url", "//host/x"]:
            with self.subTest(endpoint=endpoint):
                assert failureflags.resolveEndpoint(endpoint, None, None, None) == \
                    DEFAULT_ENDPOINT, f"endpoint {endpoint!r}"
                assert failureflags.resolveEndpoint(None, endpoint, None, None) == \
                    DEFAULT_ENDPOINT, f"endpoint {endpoint!r}"

    def test_httpAndHttpsPassThrough(self):
        for endpoint in ["http://host:1/experiment", "https://host:1/experiment",
                         "HTTP://host:1/experiment"]:
            with self.subTest(endpoint=endpoint):
                assert failureflags.resolveEndpoint(endpoint, None, None, None) == endpoint

    def test_aRejectedEndpointStillHonoursHostAndPort(self):
        assert failureflags.resolveEndpoint("file:///etc/passwd", None, "sidecar", ":6032") == \
            "http://sidecar:6032/experiment"

class TestResolveTimeout(unittest.TestCase):

    def test_defaultWhenNothingIsConfigured(self):
        assert failureflags.resolveTimeout(None, None) == failureflags.DEFAULT_TIMEOUT

    def test_precedenceAndUnits(self):
        # the argument is seconds, the environment variable is milliseconds
        assert failureflags.resolveTimeout(2, "250") == 2
        assert failureflags.resolveTimeout(None, "250") == .25
        assert failureflags.resolveTimeout(None, "1") == .001

    def test_junkFallsBackToTheDefault(self):
        for raw in ["0", "-1", "abc", "", "  "]:
            assert failureflags.resolveTimeout(None, raw) == failureflags.DEFAULT_TIMEOUT, f"timeout {raw!r}"
        for explicit in [0, -1, "5", True, None]:
            assert failureflags.resolveTimeout(explicit, None) == failureflags.DEFAULT_TIMEOUT, f"timeout {explicit!r}"

class TestFetchUsesResolvedConfiguration(unittest.TestCase):

    def setUp(self):
        body = b"[]"
        self.url_cm = MagicMock()
        self.url_cm.status = 200
        self.url_cm.read = MagicMock(return_value=body)
        self.url_cm.headers.get = MagicMock(side_effect=lambda key, default=None: {
            "Content-Type": "application/json",
            "Content-Length": str(len(body))
        }.get(key, default))
        self.url_cm.__enter__.return_value = self.url_cm

    @patch('failureflags.urlopen')
    @patch.dict(os.environ, {"FAILURE_FLAGS_ENABLED": "TRUE"})
    def test_defaultEndpointAndTimeout(self, mock_urlopen):
        mock_urlopen.return_value = self.url_cm

        failureflags.FailureFlag("name", {}, debug=True).fetch()

        request = mock_urlopen.call_args.args[0]
        assert request.full_url == DEFAULT_ENDPOINT
        assert mock_urlopen.call_args.kwargs["timeout"] == failureflags.DEFAULT_TIMEOUT

    @patch('failureflags.urlopen')
    @patch.dict(os.environ, {
        "FAILURE_FLAGS_ENABLED": "TRUE",
        "GREMLIN_SIDECAR_HOST": "sidecar",
        "GREMLIN_SIDECAR_PORT": "6000",
        "FAILURE_FLAGS_TIMEOUT_MS": "250"})
    def test_environmentConfiguresTheSidecarAndDeadline(self, mock_urlopen):
        mock_urlopen.return_value = self.url_cm

        failureflags.FailureFlag("name", {}, debug=True).fetch()

        request = mock_urlopen.call_args.args[0]
        assert request.full_url == "http://sidecar:6000/experiment"
        assert mock_urlopen.call_args.kwargs["timeout"] == .25

    @patch('failureflags.urlopen')
    @patch.dict(os.environ, {
        "FAILURE_FLAGS_ENABLED": "TRUE",
        "FAILURE_FLAGS_ENDPOINT": "http://from-variable:1/experiment",
        "FAILURE_FLAGS_TIMEOUT_MS": "250"})
    def test_keywordArgumentsBeatTheEnvironment(self, mock_urlopen):
        mock_urlopen.return_value = self.url_cm

        failureflags.FailureFlag(
            "name", {},
            debug=True,
            timeout=.5,
            endpoint="http://from-argument:2/experiment").fetch()

        request = mock_urlopen.call_args.args[0]
        assert request.full_url == "http://from-argument:2/experiment"
        assert mock_urlopen.call_args.kwargs["timeout"] == .5

if __name__ == '__main__':
    unittest.main()
