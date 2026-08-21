import logging

import failureflags
import os
import unittest
from unittest.mock import patch, MagicMock

debug = logging.getLogger("failureflags")
debug.addHandler(logging.StreamHandler())
debug.setLevel(logging.DEBUG)

def httpResponse(body=b"[]", status=200, contentType="application/json", contentLength=None):
    """Builds a mock urlopen context manager with full control over the status line and the
    headers, so the header validation in fetch() can be exercised directly."""
    headers = {}
    if contentType is not None:
        headers["Content-Type"] = contentType
    if contentLength is None and body is not None:
        contentLength = str(len(body))
    if contentLength is not None:
        headers["Content-Length"] = contentLength
    url_cm = MagicMock()
    url_cm.status = status
    url_cm.read = MagicMock(return_value=body)
    url_cm.headers.get = MagicMock(side_effect=lambda key, default=None: headers.get(key, default))
    url_cm.__enter__.return_value = url_cm
    return url_cm

EXPERIMENT = b'[{"rate":1,"effect":{"latency":10000}}]'

class TestNameIsNotTrusted(unittest.TestCase):
    """invoke() promises never to raise unless an experiment says so. A name out of a dict
    .get() or a config lookup is an ordinary way to arrive holding None."""

    @patch('failureflags.urlopen')
    @patch.dict(os.environ, {"FAILURE_FLAGS_ENABLED": "TRUE"})
    def test_aNonStringNameDoesNotRaise(self, mock_urlopen):
        mock_urlopen.return_value = httpResponse(EXPERIMENT)

        for name in [None, 7, 7.5, [], {}, b"bytes", True, ""]:
            with self.subTest(name=name):
                flag = failureflags.FailureFlag(name, {}, debug=True)

                assert flag.invoke() == (False, False, []), f"name {name!r}"

        mock_urlopen.assert_not_called(), "an unusable name must not reach the sidecar"

    @patch('failureflags.urlopen')
    @patch('failureflags.time.sleep')
    @patch.dict(os.environ, {"FAILURE_FLAGS_ENABLED": "TRUE"})
    def test_aNonCallableBehaviorDoesNotRaise(self, mock_sleep, mock_urlopen):
        mock_urlopen.return_value = httpResponse(EXPERIMENT)

        for behavior in ["defaultBehavior", 7, {}, []]:
            with self.subTest(behavior=behavior):
                flag = failureflags.FailureFlag("name", {}, behavior=behavior, debug=True)
                active, impacted, experiments = flag.invoke()

                assert active == True, f"behavior {behavior!r}: the experiment was fetched"
                assert impacted == False, f"behavior {behavior!r}: nothing could be applied"
                assert len(experiments) == 1

        mock_sleep.assert_not_called()

class TestLabelsAreNotTrusted(unittest.TestCase):

    @patch('failureflags.urlopen')
    @patch.dict(os.environ, {"FAILURE_FLAGS_ENABLED": "TRUE"})
    def test_labelsOfTheWrongTypeDoNotRaise(self, mock_urlopen):
        import json

        for labels in [None, "notadict", 7, ["a", "b"]]:
            with self.subTest(labels=labels):
                mock_urlopen.return_value = httpResponse(b"[]")

                assert failureflags.FailureFlag("name", labels, debug=True).fetch() == []

                sent = json.loads(mock_urlopen.call_args.args[0].data.decode("utf-8"))
                assert sent["labels"] == {
                    "failure-flags-sdk-version": f"python-{failureflags.VERSION}"
                }, f"labels {labels!r} should not have been sent"

class TestContentTypeIsAMediaType(unittest.TestCase):
    """`application/json; charset=utf-8` is legal and common. Matching the whole header
    exactly meant one proxy adding a parameter would silence the SDK fleet-wide."""

    @patch('failureflags.urlopen')
    @patch.dict(os.environ, {"FAILURE_FLAGS_ENABLED": "TRUE"})
    def test_parametersAndCasingAreIgnored(self, mock_urlopen):
        for header in ["application/json",
                       "application/json; charset=utf-8",
                       "application/json;charset=utf-8",
                       "Application/JSON; charset=UTF-8",
                       "  application/json  ",
                       "application/json ; charset=utf-8"]:
            with self.subTest(contentType=header):
                mock_urlopen.return_value = httpResponse(EXPERIMENT, contentType=header)

                experiments = failureflags.FailureFlag("name", {}, debug=True).fetch()

                assert len(experiments) == 1, f"Content-Type {header!r} should be accepted"

    @patch('failureflags.urlopen')
    @patch.dict(os.environ, {"FAILURE_FLAGS_ENABLED": "TRUE"})
    def test_aDifferentMediaTypeIsStillRejected(self, mock_urlopen):
        for header in ["text/html", "text/html; charset=utf-8", "", None,
                       "application/jsonp", "application/json+ld"]:
            with self.subTest(contentType=header):
                mock_urlopen.return_value = httpResponse(EXPERIMENT, contentType=header)

                assert failureflags.FailureFlag("name", {}, debug=True).fetch() == [], \
                    f"Content-Type {header!r} should be rejected"

    @patch('failureflags.urlopen')
    @patch.dict(os.environ, {"FAILURE_FLAGS_ENABLED": "TRUE"})
    def test_theNoExperimentCaseIsQuiet(self, mock_urlopen):
        # the sidecar answers "no experiments" with a bare 204, so the header validation
        # below it used to log a scary line on every single call
        mock_urlopen.return_value = httpResponse(
            body=b"", status=204, contentType=None, contentLength=None)

        with self.assertLogs("failureflags", level="DEBUG") as captured:
            assert failureflags.FailureFlag("name", {}, debug=True).fetch() == []

        noise = [m for m in captured.output if "unexpected Content-Type" in m
                                            or "invalid Content-Length" in m]
        assert noise == [], f"204 should not look like a problem: {noise}"

class TestBodyIsNotTrusted(unittest.TestCase):

    @patch('failureflags.urlopen')
    @patch.dict(os.environ, {"FAILURE_FLAGS_ENABLED": "TRUE"})
    def test_aWhitespaceOnlyBodyDoesNotRaise(self, mock_urlopen):
        # a positive Content-Length with a blank body reached json.loads("") and raised out
        # of the public fetch()
        for body in [b"   ", b"\n", b" \t\r\n "]:
            with self.subTest(body=body):
                mock_urlopen.return_value = httpResponse(body)

                assert failureflags.FailureFlag("name", {}, debug=True).fetch() == []

    @patch('failureflags.urlopen')
    @patch.dict(os.environ, {"FAILURE_FLAGS_ENABLED": "TRUE"})
    def test_aWhitespaceOnlyBodyIsNotImpact(self, mock_urlopen):
        mock_urlopen.return_value = httpResponse(b"   ")

        assert failureflags.FailureFlag("name", {}, debug=True).invoke() == (False, False, [])

    @patch('failureflags.urlopen')
    @patch.dict(os.environ, {"FAILURE_FLAGS_ENABLED": "TRUE"})
    def test_aScalarBodyIsNotAnExperiment(self, mock_urlopen):
        for body in [b"7", b'"hello"', b"null", b"true"]:
            with self.subTest(body=body):
                mock_urlopen.return_value = httpResponse(body)

                assert failureflags.FailureFlag("name", {}, debug=True).fetch() == []

if __name__ == '__main__':
    unittest.main()
