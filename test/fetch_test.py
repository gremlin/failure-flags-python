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
        url_cm.read = MagicMock(return_value="{}")
        url_cm.__enter__.return_value = url_cm
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

    def test_fetchHandlesEmptyBody(self):
        # Mock the FailureFlag class
        failure_flag = failureflags.FailureFlag("targetLatencyNumber", {}, debug=True)

        # Mock the urlopen response
        failure_flag.urlopen = MagicMock()
        failure_flag.urlopen.return_value.read = MagicMock(return_value="")  # Simulate empty body
        failure_flag.urlopen.return_value.status = 200

        # Call the fetch function
        experiments = failure_flag.fetch()

        # Assert the result is an empty list
        self.assertEqual(experiments, [])

if __name__ == '__main__':
    unittest.main()

if __name__ == '__main__':
        unittest.main()
