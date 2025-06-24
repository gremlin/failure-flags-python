import logging

from failureflags import FailureFlag
import urllib.request
import os
import unittest
from unittest.mock import patch, MagicMock

debug = logging.getLogger("failureflags")
debug.addHandler(logging.StreamHandler())
debug.setLevel(logging.DEBUG)

class TestInvoke(unittest.TestCase):


    @patch('failureflags.urlopen')
    @patch('failureflags.time.sleep')
    @patch.dict(os.environ, {"FAILURE_FLAGS_ENABLED": "TRUE"})
    def test_e2eEnabledWithLatency(self, mock_sleep, mock_urlopen):
        response_bytes = b"""[{
            "guid": "6884c0df-ed70-4bc8-84c0-dfed703bc8a7",
            "failureFlagName": "targetLatencyNumber",
            "rate": 1,
            "selector": {
              "a":"1",
              "b":"2"
            },
            "effect": {
              "latency": 10000
            }}]"""
        url_cm = MagicMock()
        url_cm.status = 200
        url_cm.read = MagicMock(return_value=response_bytes)
        url_cm.headers.get = MagicMock(side_effect=lambda key, default=None: {
            "Content-Type": "application/json",
            "Content-Length": str(len(response_bytes))
        }.get(key, default))
        url_cm.__enter__.return_value = url_cm
        mock_urlopen.return_value = url_cm
        assert "FAILURE_FLAGS_ENABLED" in os.environ

        FailureFlag("targetLatencyNumber", {}, debug=True).invoke()

        url_cm.__enter__.assert_called()
        url_cm.read.assert_called()
        mock_sleep.assert_called_with(10)

if __name__ == '__main__':
        unittest.main()
