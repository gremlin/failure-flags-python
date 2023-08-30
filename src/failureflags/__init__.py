from urllib.request import urlopen, Request
from random import random
import json
import collections
import os
import time

import logging
from logging import NullHandler

logger = logging.getLogger(__name__)
logger.addHandler(NullHandler())

VERSION = "0.0.1"

class FailureFlag:
    """FailureFlag represents a point in your code where you want to be able to inject failures dynamically.
    
    The FailureFlag object can be created anywhere and will only have an effect at the line where the 
    invoke() function is called. Instead of relying on the built-in behavior processing a user can call the
    fetch() function to simply retrieve any active experiments targeting a FailureFlag.

    This package is inert if the FAILURE_FLAGS_ENABLED environment variable is unset.
    """

    def __init__(self, name, labels, behavior=None, data={}, debug=False):
        """Create a new FailureFlag.

        Keyword arguments:
        behavior -- a function to invoke for retrieved experiments instead of the default behavior chain.
        debug -- True or False (default False) to control debug logging.
        data -- Data to be mutated by behaviors and effect data.
        """
        
        self.enabled = 'FAILURE_FLAGS_ENABLED' in os.environ
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
            if self.debug:
                logger.debug("SDK not enabled")
            return (active, impacted, experiments)
        if len(self.name) <= 0:
            if self.debug:
                logger.debug("no failure flag name specified")
            return (active, impacted, experiments)
        try:
            experiments = self.fetch()
        except Exception as err:
            if self.debug:
                logger.debug("received error while fetching experiments", err)
            return (active, impacted, experiments)
        if len(experiments) > 0:
            active = True
            # TODO dice roll
            dice = random()
            filteredExperiments = filter(lambda experiment: 
                                         (type(experiment["rate"]) is float 
                                         or type(experiment["rate"]) is int)
                                         and experiment["rate"] >= 0 
                                         and experiment["rate"] <= 1 
                                         and dice < experiment["rate"], experiments)
            impacted = self.behavior(self, list(filteredExperiments))
        else:
            if self.debug:
                logger.debug("no experiments retrieved")
        return (active, impacted, experiments)

    def fetch(self):
        global logger
        global VERSION
        experiments = []
        if not self.enabled:
            return experiments
        self.labels["failure-flags-sdk-version"] = f"python-v{VERSION}"
        data = json.dumps({"name": self.name, "labels": self.labels}).encode("utf-8")
        request = Request('http://localhost:5032/experiment',
                          headers={"Content-Type": "application/json", "Content-Length": len(data)}, 
                          data=data)
        with urlopen(request, timeout=.001) as response:
            code = 0
            if hasattr(response, 'status'):
                code = response.status
            if code < 200 or code >= 300:
                if self.debug:
                    logger.debug(f"bad status code ({code}) while fetching experiments")
                return []

            # TODO validate Content-Type
            # TODO validate Content-Length
            body = response.read()
            response.close()
            experiments = json.loads(body)
            if isinstance(experiments, list) or type(experiments) is list:
                return experiments
            elif isinstance(experiments, dict) or type(experiments) is dict:
                return [experiments]
            else:
                return []

# behaviors take a ff and a list of experiments and return (impacted)

def delayedDataOrError(failureflag, experiments):
    latencyImpact = latency(failureflag, experiments)
    exceptionImpact = exception(failureflag, experiments)
    dataImpact = data(failureflag, experiments)
    return latencyImpact or exceptionImpact or dataImpact

def latency(ff, experiments):
    impacted = False
    if experiments == None or len(experiments) == 0:
        if ff.debug:
            logger.debug("experiments was empty")
        return impacted
    for e in experiments:
        if not isinstance(e, dict) or type(e) is not dict:
            if ff.debug:
                logger.debug("experiment is not a dict, skipping")
            continue
        if "effect" not in e:
            if ff.debug:
                logger.debug("no effect in experiment, skipping")
            continue
        if "latency" not in e["effect"]:
            if ff.debug:
                logger.debug("no latency in experiment effect, skipping")
            continue
        if type(e["effect"]["latency"]) is int:
            impacted = True
            time.sleep(e["effect"]["latency"]/1000)
        elif type(e["effect"]["latency"]) is str:
            try: 
                ms = int(e["effect"]["latency"])
                time.sleep(ms/1000)
                impacted = True
            except ValueError as err:
                if ff.debug:
                    logger.debug("experiment contained a non-number latency clause")
        elif isinstance(e["effect"]["latency"], dict):
            impacted = True
            ms = 0
            jitter = 0
            if "ms" in e["effect"]["latency"] and type(e["effect"]["latency"]["ms"]) is int:
                ms = e["effect"]["latency"]["ms"]
            if "jitter" in e["effect"]["latency"] and type(e["effect"]["latency"]["jitter"]) is int:
                jitter = e["effect"]["latency"]["jitter"]
            # convert both ms and jitter to seconds
            time.sleep(ms/1000 + jitter*random()/1000)
    return impacted

def exception(ff, experiments):
    global logger
    for f in experiments:
        if not isinstance(f, dict) or type(f) is not dict:
            continue
        if "effect" not in f:
            continue
        if "exception" not in f["effect"]:
            continue
        if type(f["effect"]["exception"]) is str:
            raise ValueError(f["effect"]["exception"])
        elif isinstance(f["effect"]["exception"], dict):
            module = "builtins"
            class_name = "ValueError"
            message = "Error injected via Gremlin Failure Flags (default message)"
            hasKnown = False
            if "module" in f["effect"]["exception"] and type(f["effect"]["exception"]["module"]) is str:
                module = f["effect"]["exception"]["module"]
                hasKnown = True
            if "className" in f["effect"]["exception"] and type(f["effect"]["exception"]["className"]) is str:
                class_name= f["effect"]["exception"]["className"]
                hasKnown = True
            if "message" in f["effect"]["exception"] and type(f["effect"]["exception"]["message"]) is str:
                message = f["effect"]["exception"]["message"]
                hasKnown = True
            if not hasKnown:
                if ff.debug:
                    logger.debug("exception clause was not populated")
                continue
            if len(class_name) == 0:
                # for some reason this was explicitly unset
                continue
            error = None
            try:
                if module is not None:
                    module_ = __import__(module, fromlist=[None])
                    class_ = getattr(module_, class_name)
                else: 
                    class_ = globals()[class_name]
                error = class_(message)
            except Exception as err:
                # unable to load the class
                if ff.debug:
                    logger.debug(f"unable to load the named module: {module}, {err}")
                return False
            if error is not None:
                raise error
    return False

def data(ff, experiments):
    return False

defaultBehavior = delayedDataOrError
