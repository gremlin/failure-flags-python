import logging

import failureflags
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

        flag = failureflags.FailureFlag("targetLatencyNumber", {}, debug=True)
        print(flag)
        active, impacted, experiments = flag.invoke()
        print(active, impacted, experiments)

        print(mock_urlopen)
        url_cm.__enter__.assert_called()
        url_cm.read.assert_called()
        mock_sleep.assert_called_with(10)
        assert len(experiments) == 1
        assert experiments[0]["failureFlagName"] == "targetLatencyNumber"
        assert active == True, "works should be Active"
        assert impacted == True, "works should be Impacted"

    @patch('failureflags.urlopen')
    @patch('failureflags.time.sleep')
    @patch.dict(os.environ, clear=True)
    def test_e2eInert(self, mock_sleep, mock_urlopen):
        url_cm = MagicMock()
        url_cm.status = 200
        url_cm.read = MagicMock(return_value="""[{
            "guid": "6884c0df-ed70-4bc8-84c0-dfed703bc8a7",
            "failureFlagName": "works",
            "rate": 1,
            "selector": {
              "a":"1",
              "b":"2"
            },
            "effect": {
              "latency": 10
            }}]""")
        url_cm.__enter__.return_value = url_cm
        mock_urlopen.return_value = url_cm

        assert "FAILURE_FLAGS_ENABLED" not in os.environ

        flag = failureflags.FailureFlag("works", {}, debug=True)
        active, impacted, experiments = flag.invoke()

        url_cm.__enter__.assert_not_called();
        url_cm.read.assert_not_called();
        mock_sleep.assert_not_called();
        assert len(experiments) == 0
        assert active == False, "works should be inactive because the SDK should be inert"
        assert impacted == False , "works should not be impacted because the SDK should be inert"

        url_cm.headers.get = MagicMock(side_effect=lambda key, default=None: {
            "Content-Type": "application/json",
            "Content-Length": str(len(response_bytes))
        }.get(key, default))

if __name__ == '__main__':
        unittest.main()
