from urllib.request import urlopen, Request
import json
import collections
import os
import time

import logging
from logging import NullHandler

logger = logging.getLogger(__name__)
logger.addHandler(NullHandler())

class FailureFlag:
    enabled = True if os.environ.get('FAILURE_FLAGS_ENABLED') != None else False

    def __init__(self, name, labels, behavior=None, data={}, debug=False):
        self.name = name
        self.labels = labels
        self.behavior = behavior if behavior != None else defaultBehavior
        self.data = data 
        self.debug = True if debug != False else False # filter out any other possible values that might be provided

    def __str__(self):
        return f"<FailureFlag name:{self.name} labels:{self.labels} debug:{self.debug}>"

    def invoke(self):
        global logger
        active = False
        impacted = False
        experiments = []
        if not self.enabled:
            return (active, impacted, experiments)
        if len(self.name) <= 0:
            if self.debug:
                logger.debug("no failure flag name specified")
            return (active, impacted, experiments)
        try:
            experiments = self.fetch()
        except Exception as err:
            if self.debug:
                logger.debug("received error while fetching experiments")
            return (active, impacted, experiments)
        if len(experiments) > 0:
            active = True
            impacted = self.behavior(self, experiments)
        return (active, impacted, experiments)

    def fetch(self):
        global logger
        experiments = []
        if not self.enabled:
            return experiments
        data = json.dumps({"name": self.name, "labels": self.labels}).encode("utf-8")
        request = Request('http://localhost:5032/experiment', headers={"Content-Type": "application/json", "Content-Length": len(data)}, data=data)
        with urlopen(request, timeout=.001) as response:
            # validate status code
            code = 0
            if hasattr(response, 'status'):
                code = response.status
            elif hasattr(response, 'code'):
                code = response.code
            if code < 200 or code >= 300:
                if self.debug:
                    logger.debug("bad status code ({}) while fetching experiments".format(code))
                return []

            # validate Content-Type
            # validate Content-Length
            body = response.read()
            response.close()
            experiments = json.loads(body)
            if isinstance(experiments, collections.list) or type(experiments) is list:
                return experiments
            elif isinstance(experiments, collections.Mapping) or type(experiments) is dict:
                return [experiments]
            else:
                return []

# behaviors take a ff and a list of experiments and return (impacted)

def delayedDataOrError(failureflag, experiments):
    latencyImpact = latency(failureflag, experiments)
    exceptionImpact = exception(failureflag, experiments)
    dataImpact = data(failureflag, experiments)
    return latencyImpact or exceptionImpact or dataImpact

def latency(failureflag, experiments):
    impacted = False
    if experiments == None or len(experiments) == 0:
        return impacted
    for f in experiments:
        if not isinstance(f, collections.Mapping) or type(f) is not dict:
            continue
        if "effect" not in f:
            continue
        if "latency" not in f["effect"]:
            continue
        if type(f["effect"]["latency"]) is int:
            impacted = True
            time.sleep(f["effect"]["latency"]/1000)
        elif isinstance(f["effect"]["latency"], collections.Mapping):
            impacted = True
            ms = 0
            jitter = 0
            if "ms" in f["effect"]["latency"] and f["effect"]["latency"]["ms"] is int:
                ms = f["effect"]["latency"]["ms"]
            if "jitter" in f["effect"]["latency"] and f["effect"]["latency"]["jitter"] is int:
                jitter = f["effect"]["latency"]["jitter"]
            # convert both ms and jitter to seconds
            time.sleep(ms/1000 + jitter*random.random()/1000)
    return impacted

def exception(failureflag, experiments):
    global logger
    for f in experiments:
        if not isinstance(f, collections.Mapping) or type(f) is not dict:
            continue
        if "effect" not in f:
            continue
        if "exception" not in f["effect"]:
            continue
        if type(f["effect"]["exception"]) is str:
            raise ValueException(f["effect"]["exception"])
        elif isinstance(f["effect"]["exception"], collections.Mapping):
            module = None
            class_name = "ValueException"
            message = "Error injected via Gremlin Failure Flags (default message)"
            hasKnown = False
            if "module" in f["effect"]["exception"] and f["effect"]["exception"]["module"] is str:
                module = f["effect"]["exception"]["module"]
                hasKnown = True
            if "className" in f["effect"]["exception"] and f["effect"]["exception"]["className"] is str:
                class_name= f["effect"]["exception"]["className"]
                hasKnown = True
            if "message" in f["effect"]["exception"] and f["effect"]["exception"]["message"] is str:
                message = f["effect"]["exception"]["message"]
                hasKnown = True
            if not hasKnown:
                continue
            if len(class_name) == 0:
                # for some reason this was explicitly unset
                continue
            error = None
            try:
                if module is not None:
                    module_ = __import__(module)
                    class_ = getattr(module_, class_name)
                else: 
                    class_ = globals()[class_name]
                error = class_(message)
            except:
                # unable to load the class
                if failureflag.debug:
                    logger.debug("unable to load the named module: {}", module)
            if error is not None:
                raise error
    return False

def data(failureflag, experiments):
    return False

defaultBehavior = delayedDataOrError
