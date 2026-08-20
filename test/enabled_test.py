import failureflags
import os
import unittest
from unittest.mock import patch, MagicMock

def jsonResponse(body):
    """Builds a mock urlopen context manager that answers with `body`."""
    url_cm = MagicMock()
    url_cm.status = 200
    url_cm.read = MagicMock(return_value=body)
    url_cm.headers.get = MagicMock(side_effect=lambda key, default=None: {
        "Content-Type": "application/json",
        "Content-Length": str(len(body))
    }.get(key, default))
    url_cm.__enter__.return_value = url_cm
    return url_cm

class TestEnabled(unittest.TestCase):

    def test_isEnabledAcceptsTheDocumentedValues(self):
        for raw in ["true", "TRUE", "True", " true ", "yes", "YES", "1", " 1 "]:
            assert failureflags.isEnabled(raw) == True, f"{raw!r} should enable the SDK"

    def test_isEnabledRejectsEverythingElse(self):
        # "false" is the value the install docs tell proxy-mode users to set. It must
        # never enable the SDK.
        for raw in [None, "", " ", "false", "FALSE", "no", "0", "banana", "truthy", "2"]:
            assert failureflags.isEnabled(raw) == False, f"{raw!r} should not enable the SDK"

    @patch('failureflags.urlopen')
    @patch.dict(os.environ, {"FAILURE_FLAGS_ENABLED": "false"})
    def test_invokeIsInertWhenExplicitlyDisabled(self, mock_urlopen):
        mock_urlopen.return_value = jsonResponse(b'[{"rate":1,"effect":{"latency":1}}]')

        flag = failureflags.FailureFlag("name", {}, debug=True)
        active, impacted, experiments = flag.invoke()

        assert flag.enabled == False, "FAILURE_FLAGS_ENABLED=false must not enable the SDK"
        mock_urlopen.assert_not_called()
        assert (active, impacted, experiments) == (False, False, [])

    @patch('failureflags.urlopen')
    def test_enabledIsReadFromTheEnvironmentOnEveryCall(self, mock_urlopen):
        mock_urlopen.return_value = jsonResponse(b'[]')

        # constructed while the SDK is disabled, the way a module-level flag is built
        # before the process environment is fully configured
        with patch.dict(os.environ, clear=True):
            flag = failureflags.FailureFlag("name", {}, debug=True)
            assert flag.enabled == False

        with patch.dict(os.environ, {"FAILURE_FLAGS_ENABLED": "1"}):
            assert flag.enabled == True
            flag.invoke()

        mock_urlopen.assert_called()

    @patch.dict(os.environ, {"FAILURE_FLAGS_ENABLED": "true"})
    def test_enabledIsReadOnly(self):
        # through 1.0.3 this was a plain attribute; the README documents the migration
        flag = failureflags.FailureFlag("name", {}, debug=True)
        with self.assertRaises(AttributeError):
            flag.enabled = False
        assert flag.enabled == True

if __name__ == '__main__':
    unittest.main()
