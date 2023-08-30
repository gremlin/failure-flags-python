import logging

import failureflags
import unittest
from unittest.mock import patch, call

debug = logging.getLogger("failureflags")
debug.addHandler(logging.StreamHandler())
debug.setLevel(logging.DEBUG)

class TestFailureFlagsBehaviors(unittest.TestCase):

    ##################################################
    # Testing the latency behavior
    ##################################################

    @patch('failureflags.time.sleep')
    def test_latencyNoExperiments(self, mock_sleep):
        impacted = failureflags.latency(failureflags.FailureFlag("name", {}), [])
        mock_sleep.assert_not_called()
        assert impacted == False, "impact reported when no experiments were provided"

    @patch('failureflags.time.sleep')
    def test_latencyOneExperimentNoLatency(self, mock_sleep):
        impacted = failureflags.latency(failureflags.FailureFlag("name", {}), [{
           "guid": "6884c0df-ed70-4bc8-84c0-dfed703bc8a7",
           "failureFlagName": "custom",
           "rate": 1,
           "selector": {
               "a":"1",
               "b":"2"
           },
           "effect": {
               "custom": "10",
           }}])
        mock_sleep.assert_not_called()
        assert impacted == False, "impact reported when no experiments were provided"

    @patch('failureflags.time.sleep')
    def test_latencyOneExperimentWithLatencyNumber(self, mock_sleep):
        impacted = failureflags.latency(failureflags.FailureFlag("name", {}), [{
           "guid": "6884c0df-ed70-4bc8-84c0-dfed703bc8a7",
           "failureFlagName": "custom",
           "rate": 1,
           "selector": {
               "a":"1",
               "b":"2"
           },
           "effect": {
               "latency": 10000,
           }}])
        mock_sleep.assert_called()
        assert impacted == True, "No impact reported when latency experiments were provided"

    @patch('failureflags.time.sleep')
    def test_latencyOneExperimentWithLatencyString(self, mock_sleep):
        impacted = failureflags.latency(failureflags.FailureFlag("name", {}), [{
           "guid": "6884c0df-ed70-4bc8-84c0-dfed703bc8a7",
           "failureFlagName": "custom",
           "rate": 1,
           "selector": {
               "a":"1",
               "b":"2"
           },
           "effect": {
               "latency": "10000",
           }}])
        mock_sleep.assert_called()
        assert impacted == True, "No impact reported when latency experiments were provided"

    @patch('failureflags.time.sleep')
    def test_latencyOneExperimentWithBadLatencyString(self, mock_sleep):
        impacted = failureflags.latency(failureflags.FailureFlag("name", {}), [{
           "guid": "6884c0df-ed70-4bc8-84c0-dfed703bc8a7",
           "failureFlagName": "custom",
           "rate": 1,
           "selector": {
               "a":"1",
               "b":"2"
           },
           "effect": {
               "latency": "notanumber",
           }}])
        mock_sleep.assert_not_called()
        assert impacted == False, "Impact reported when bad latency experiments were provided"

    @patch('failureflags.time.sleep')
    def test_latencyOneExperimentWithDictLatency(self, mock_sleep):
        impacted = failureflags.latency(failureflags.FailureFlag("name", {}, debug=True), [{
           "guid": "6884c0df-ed70-4bc8-84c0-dfed703bc8a7",
           "failureFlagName": "custom",
           "rate": 1,
           "selector": {
               "a":"1",
               "b":"2"
           },
           "effect": {
               "latency": {
                   "ms": 10000,
                   "jitter": 0
                },
           }}])
        mock_sleep.assert_called_with(10)
        assert impacted == True, "No impact reported when latency experiments were provided"

    @patch('failureflags.time.sleep')
    def test_latencyTwoExperimentsWithDictLatency(self, mock_sleep):
        impacted = failureflags.latency(failureflags.FailureFlag("name", {}, debug=True), [{
           "guid": "6884c0df-ed70-4bc8-84c0-dfed703bc8a7",
           "failureFlagName": "name",
           "rate": 1,
           "selector": {
               "a":"1",
               "b":"2"
           },
           "effect": {
               "latency": 10000
           }},{
           "guid": "6884c0df-ed70-4bc8-84c0-dfed703bc8a8",
           "failureFlagName": "name",
           "rate": 1,
           "selector": {
               "a":"1",
               "b":"2"
           },
           "effect": {
               "latency": 20000
           }}])
        mock_sleep.assert_has_calls([call(10), call(20)])
        assert impacted == True, "No impact reported when latency experiments were provided"

    ##################################################
    # Testing the exception behavior
    ##################################################

    def test_exceptionNoExperiments(self):
        try:
            impacted = failureflags.exception(failureflags.FailureFlag("name", {}, debug=True), [])
        except Exception as err:
            assert false, "No exception should be raised when no experiments are provided"

    def test_exceptionNoExceptionEffect(self):
        try:
            impacted = failureflags.exception(failureflags.FailureFlag("name", {}, debug=True), [{
                "guid": "6884c0df-ed70-4bc8-84c0-dfed703bc8a8",
                "failureFlagName": "name",
                "rate": 1,
                "selector": {
                    "a":"1",
                    "b":"2"
                },
                "effect": {
                   "latency": 20000
                }}])
        except Exception as err:
            assert false, "No exception should be raised when no experiments have exception effects"

    def test_exceptionSimpleExceptionEffect(self):
        try:
            impacted = failureflags.exception(failureflags.FailureFlag("name", {}, debug=True), [{
                "guid": "6884c0df-ed70-4bc8-84c0-dfed703bc8a8",
                "failureFlagName": "name",
                "rate": 1,
                "selector": {
                    "a":"1",
                    "b":"2"
                },
                "effect": {
                    "exception": "this is a test message"
                }}])
        except Exception as err:
            assert err.args[0] == "this is a test message"
            return
        assert False, "An exception must be raised if the experiment provides a valid exception clause"

    def test_exceptionDictExceptionEffect(self):
        try:
            impacted = failureflags.exception(failureflags.FailureFlag("name", {}), [{
                "guid": "6884c0df-ed70-4bc8-84c0-dfed703bc8a8",
                "failureFlagName": "name",
                "rate": 1,
                "selector": {
                    "a":"1",
                    "b":"2"
                },
                "effect": {
                    "exception": {
                        "module": "http.client",
                        "className": "ImproperConnectionState",
                        "message": "this is an improper connection state error"
                    }
                }}])
        except Exception as err:
            assert err.args[0] == "this is an improper connection state error"
            assert err.__class__.__name__ == "ImproperConnectionState"
            return
        assert False, "An exception must be raised if the experiment provides a valid exception clause"

    def test_exceptionPartialDictExceptionEffect(self):
        try:
            impacted = failureflags.exception(failureflags.FailureFlag("name", {}), [{
                "guid": "6884c0df-ed70-4bc8-84c0-dfed703bc8a8",
                "failureFlagName": "name",
                "rate": 1,
                "selector": {
                    "a":"1",
                    "b":"2"
                },
                "effect": {
                    "exception": {
                        "className": "TimeoutError",
                        "message": "this is an improper connection state error"
                    }
                }}])
        except Exception as err:
            assert err.args[0] == "this is an improper connection state error"
            assert err.__class__.__name__ == "TimeoutError"
            return
        assert False, "An exception must be raised if the experiment provides a valid exception clause"

    ##################################################
    # Testing the delayedDataOrError behavior
    ##################################################

    @patch('failureflags.time.sleep')
    def test_delayedException(self, mock_sleep):
        try:
            impacted = failureflags.delayedDataOrError(failureflags.FailureFlag("name", {}, debug=True), [{
                "guid": "6884c0df-ed70-4bc8-84c0-dfed703bc8a8",
                "failureFlagName": "name",
                "rate": 1,
                "selector": {
                    "a":"1",
                    "b":"2"
                },
                "effect": {
                    "latency": 10000,
                    "exception": "this is a test message"
                }}])
        except Exception as err:
            mock_sleep.assert_called_with(10)
            assert err.args[0] == "this is a test message"
            return
        assert False, "An exception must be raised if the experiment provides a valid exception clause"

if __name__ == '__main__':
        unittest.main()
