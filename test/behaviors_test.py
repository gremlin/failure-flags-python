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

    def test_exceptionDocumentedNameKey(self):
        # the payload from the error-metadata docs: `name`, not `className`
        try:
            failureflags.exception(failureflags.FailureFlag("name", {}, debug=True), [{
                "guid": "6884c0df-ed70-4bc8-84c0-dfed703bc8a8",
                "failureFlagName": "name",
                "rate": 1,
                "effect": {
                    "exception": {
                        "message": "this is a custom error",
                        "name": "TimeoutError"
                    }
                }}])
        except Exception as err:
            assert err.args[0] == "this is a custom error"
            assert err.__class__.__name__ == "TimeoutError"
            return
        assert False, "An exception must be raised if the experiment provides a valid exception clause"

    def test_exceptionNameWithModule(self):
        try:
            failureflags.exception(failureflags.FailureFlag("name", {}, debug=True), [{
                "rate": 1,
                "effect": {
                    "exception": {
                        "module": "http.client",
                        "name": "ImproperConnectionState",
                        "message": "this is an improper connection state error"
                    }
                }}])
        except Exception as err:
            assert err.args[0] == "this is an improper connection state error"
            assert err.__class__.__name__ == "ImproperConnectionState"
            return
        assert False, "An exception must be raised if the experiment provides a valid exception clause"

    def test_exceptionClassNameBeatsName(self):
        try:
            failureflags.exception(failureflags.FailureFlag("name", {}, debug=True), [{
                "rate": 1,
                "effect": {
                    "exception": {
                        "name": "TimeoutError",
                        "className": "KeyError",
                        "message": "className wins"
                    }
                }}])
        except Exception as err:
            assert err.__class__.__name__ == "KeyError"
            return
        assert False, "An exception must be raised if the experiment provides a valid exception clause"

    def test_exceptionUnloadableNameStillRaises(self):
        # a name that exists in no module: raising nothing would report impact while the
        # application saw no failure at all
        try:
            failureflags.exception(failureflags.FailureFlag("name", {}, debug=True), [{
                "rate": 1,
                "effect": {
                    "exception": {
                        "name": "CustomErrorType",
                        "message": "this is a custom error"
                    }
                }}])
        except Exception as err:
            assert err.args[0] == "this is a custom error"
            assert err.__class__.__name__ == "ValueError"
            return
        assert False, "An unloadable exception name must still raise something"

    def test_exceptionUnloadableModuleStillRaises(self):
        try:
            failureflags.exception(failureflags.FailureFlag("name", {}, debug=True), [{
                "rate": 1,
                "effect": {
                    "exception": {
                        "module": "no.such.module",
                        "className": "TimeoutError",
                        "message": "this is a custom error"
                    }
                }}])
        except Exception as err:
            assert err.args[0] == "this is a custom error"
            assert err.__class__.__name__ == "ValueError"
            return
        assert False, "An unloadable module must still raise something"

    def test_exceptionExplicitlyEmptyClassNameRaisesNothing(self):
        impacted = failureflags.exception(failureflags.FailureFlag("name", {}, debug=True), [{
            "rate": 1,
            "effect": {
                "exception": {
                    "className": "",
                    "message": "this should not be raised"
                }
            }}])
        assert impacted == False, "an explicitly empty className opts out of the exception effect"

    def test_exceptionEmptyClauseRaisesNothing(self):
        impacted = failureflags.exception(failureflags.FailureFlag("name", {}, debug=True), [{
            "rate": 1,
            "effect": {
                "exception": {}
            }}])
        assert impacted == False, "an unpopulated exception clause opts out of the exception effect"

    def test_exceptionNonExceptionClassNameStillRaisesCleanly(self):
        # `str` loads fine but is not an exception type: raising it would throw a TypeError
        # of the SDK's own making out of the caller's line
        try:
            failureflags.exception(failureflags.FailureFlag("name", {}, debug=True), [{
                "rate": 1,
                "effect": {
                    "exception": {
                        "className": "str",
                        "message": "this is a custom error"
                    }
                }}])
        except Exception as err:
            assert err.args[0] == "this is a custom error"
            assert err.__class__.__name__ == "ValueError"
            return
        assert False, "A className that is not an exception type must still raise something"

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

    @patch('failureflags.time.sleep')
    def test_behaviorsSkipExperimentsWithoutADictEffect(self, mock_sleep):
        # a malformed effect must not stop the effects that follow it in the list
        experiments = [
            {"rate": 1, "effect": None},
            {"rate": 1, "effect": "latency"},
            {"rate": 1, "effect": {"latency": 10000, "exception": "this is a test message"}}]
        try:
            failureflags.delayedDataOrError(failureflags.FailureFlag("name", {}, debug=True), experiments)
        except Exception as err:
            mock_sleep.assert_called_with(10)
            assert err.args[0] == "this is a test message"
            return
        assert False, "the well-formed experiment in the list must still be applied"

if __name__ == '__main__':
        unittest.main()
