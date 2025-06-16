import logging

import failureflags
import urllib.request
import os
import unittest
from unittest.mock import patch, MagicMock

debug = logging.getLogger("failureflags")
debug.addHandler(logging.StreamHandler())
debug.setLevel(logging.DEBUG)

class TestFetch(unittest.TestCase):

    @patch('failureflags.urlopen')
    @patch.dict(os.environ, clear=True)
    def test_inert(self, mock_urlopen):
        url_cm = MagicMock()
        url_cm.status = 200
        url_cm.read = MagicMock(side_effect=Exception("should not be used"), return_value="[{}]")
        url_cm.__enter__.return_value = url_cm
        mock_urlopen.return_value = url_cm

        assert "FAILURE_FLAGS_ENABLED" not in os.environ

        experiments = []
        try:
            experiments = failureflags.FailureFlag("name", {}, debug=True).fetch()
        except Exception as err:
            assert False, "an inert SDK will not throw an Exception when running fetch"

    @patch('failureflags.urlopen')
    @patch.dict(os.environ, {"FAILURE_FLAGS_ENABLED": "TRUE"})
    def test_fetchWrapsSingleExperimentWithList(self, mock_urlopen):
        url_cm = MagicMock()
        url_cm.status = 200
        url_cm.read = MagicMock(return_value=b"{}")  # Return bytes instead of a string
        url_cm.__enter__.return_value = url_cm
        url_cm.headers.get = MagicMock(side_effect=lambda key, default=None: {
            "Content-Type": "application/json",
            "Content-Length": "2"  # Valid Content-Length matching the body size
        }.get(key, default))  # Mock headers.get() to return valid values
        mock_urlopen.return_value = url_cm
        assert "FAILURE_FLAGS_ENABLED" in os.environ

        experiments = []
        try:
            experiments = failureflags.FailureFlag("targetLatencyNumber", {}, debug=True).fetch()
        except Exception as err:
            assert False, "an inert SDK will not throw an Exception when running fetch"

        url_cm.__enter__.assert_called()
        url_cm.read.assert_called()
        assert len(experiments) == 1

    @patch('failureflags.urlopen')
    @patch.dict(os.environ, {"FAILURE_FLAGS_ENABLED": "TRUE"})
    def test_fetchHandlesNon200CodeSilently(self, mock_urlopen):
        url_cm = MagicMock()
        url_cm.status = 400
        url_cm.read = MagicMock(return_value="[{}]")
        url_cm.__enter__.return_value = url_cm
        mock_urlopen.return_value = url_cm
        assert "FAILURE_FLAGS_ENABLED" in os.environ

        experiments = []
        try:
            experiments = failureflags.FailureFlag("targetLatencyNumber", {}, debug=True).fetch()
        except Exception as err:
            assert False, "an inert SDK will not throw an Exception when running fetch"

        url_cm.__enter__.assert_called()
        url_cm.read.assert_not_called()
        assert len(experiments) == 0

    @patch('failureflags.urlopen')
    @patch.dict(os.environ, {"FAILURE_FLAGS_ENABLED": "TRUE"})
    def test_fetchHandlesEmptyBody(self, mock_urlopen):
        url_cm = MagicMock()
        url_cm.status = 200
        url_cm.read = MagicMock(return_value="")
        url_cm.__enter__.return_value = url_cm
        mock_urlopen.return_value = url_cm
        assert "FAILURE_FLAGS_ENABLED" in os.environ

        failure_flag = failureflags.FailureFlag("targetLatencyNumber", {}, debug=True)

        # Call the fetch function
        experiments = failure_flag.fetch()

        # Assert the result is an empty list
        self.assertEqual(experiments, [])

    @patch('failureflags.urlopen')
    @patch.dict(os.environ, {"FAILURE_FLAGS_ENABLED": "TRUE"})
    def test_fetchHandlesInvalidContentType(self, mock_urlopen):
        url_cm = MagicMock()
        url_cm.status = 200
        url_cm.read = MagicMock(side_effect=Exception("read() should not be called"))  # Raise exception if called
        url_cm.__enter__.return_value = url_cm
        url_cm.headers = {"Content-Type": "text/plain"}  # Invalid Content-Type
        mock_urlopen.return_value = url_cm

        try:
            experiments = failureflags.FailureFlag("targetLatencyNumber", {}, debug=True).fetch()
            self.assertEqual(experiments, [])  # Should return an empty list
        except Exception as err:
            self.fail(f"fetch raised an unexpected exception: {err}")

        url_cm.__enter__.assert_called()

    @patch('failureflags.urlopen')
    @patch.dict(os.environ, {"FAILURE_FLAGS_ENABLED": "TRUE"})
    def test_fetchHandlesInvalidContentLength(self, mock_urlopen):
        url_cm = MagicMock()
        url_cm.status = 200
        url_cm.read = MagicMock(return_value="[{}]")
        url_cm.__enter__.return_value = url_cm
        url_cm.headers = {"Content-Type": "application/json", "Content-Length": "-1"}  # Invalid Content-Length
        mock_urlopen.return_value = url_cm

        experiments = []
        try:
            experiments = failureflags.FailureFlag("targetLatencyNumber", {}, debug=True).fetch()
        except Exception as err:
            assert False, "fetch should not throw an Exception for invalid Content-Length"

        url_cm.__enter__.assert_called()
        url_cm.read.assert_not_called()  # Body should not be read
        assert len(experiments) == 0  # Should return an empty list

if __name__ == '__main__':
    unittest.main()

