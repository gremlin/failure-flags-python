import failureflags
import json
import os
import unittest
from unittest.mock import patch, MagicMock

class TestFailureFlag(unittest.TestCase):

    def test_dataIsNotSharedBetweenFlags(self):
        a = failureflags.FailureFlag("a", {"x": "1"})
        b = failureflags.FailureFlag("b", {"y": "2"})

        a.data["leaked"] = "from a"

        assert b.data == {}, "flags built without an explicit data= must not share one dict"
        assert failureflags.FailureFlag("c", {}).data == {}

    def test_dataUsesTheProvidedDict(self):
        provided = {"k": "v"}
        assert failureflags.FailureFlag("a", {}, data=provided).data is provided

    @patch('failureflags.urlopen')
    @patch.dict(os.environ, {"FAILURE_FLAGS_ENABLED": "TRUE"})
    def test_fetchDoesNotMutateTheCallersLabels(self, mock_urlopen):
        body = b"[]"
        url_cm = MagicMock()
        url_cm.status = 200
        url_cm.read = MagicMock(return_value=body)
        url_cm.headers.get = MagicMock(side_effect=lambda key, default=None: {
            "Content-Type": "application/json",
            "Content-Length": str(len(body))
        }.get(key, default))
        url_cm.__enter__.return_value = url_cm
        mock_urlopen.return_value = url_cm

        # the natural way to label by deployment: one dict, reused
        caller = {"method": "GET"}
        failureflags.FailureFlag("name", caller, debug=True).fetch()

        assert caller == {"method": "GET"}, "fetch must not write into the caller's dict"

        # ... and the sidecar still gets the version label
        request = mock_urlopen.call_args.args[0]
        sent = json.loads(request.data.decode("utf-8"))
        assert sent["labels"]["method"] == "GET"
        assert sent["labels"]["failure-flags-sdk-version"] == f"python-{failureflags.VERSION}"

if __name__ == '__main__':
    unittest.main()
