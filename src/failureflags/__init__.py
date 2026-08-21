from urllib.request import urlopen, Request
from random import random
from math import isfinite
import json
import os
import time

import logging
from logging import NullHandler

logger = logging.getLogger(__name__)
logger.addHandler(NullHandler())

VERSION = "1.1.0"

ENV_ENABLED = "FAILURE_FLAGS_ENABLED"
ENV_ENDPOINT = "FAILURE_FLAGS_ENDPOINT"
ENV_TIMEOUT_MS = "FAILURE_FLAGS_TIMEOUT_MS"
ENV_SIDECAR_HOST = "GREMLIN_SIDECAR_HOST"
ENV_SIDECAR_PORT = "GREMLIN_SIDECAR_PORT"

# The values of FAILURE_FLAGS_ENABLED that turn the SDK on.
ENABLED_VALUES = frozenset(("true", "yes", "1"))

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 5032
DEFAULT_TIMEOUT = .001 # seconds

# The sidecar speaks HTTP. Anything else in FAILURE_FLAGS_ENDPOINT is a misconfiguration,
# and urlopen would happily honour file:// or ftp:// if we passed it along.
ALLOWED_SCHEMES = ("http://", "https://")

def cleanString(value):
    """Returns `value` trimmed if it is a non-empty string, otherwise None."""
    if type(value) is not str:
        return None
    value = value.strip()
    return value if len(value) > 0 else None

def isEnabled(raw):
    """True when `raw` is one of the documented enabling values: `true`, `yes`, or `1`,
    case-insensitive. Absent, empty, and anything else means disabled.

    Testing for the presence of the variable rather than its value would make
    FAILURE_FLAGS_ENABLED=false *enable* fault injection, which is the wrong direction
    for a kill switch.
    """
    return raw is not None and raw.strip().lower() in ENABLED_VALUES

def parsePort(raw, debug=False):
    """Extracts a TCP port from a GREMLIN_SIDECAR_PORT value, or None if there isn't one.

    The sidecar reads this variable as a *listen address* and requires a colon, so in a Pod
    where both containers share it -- the whole reason for reusing the sidecar's name -- the
    value is `:6032`, `0.0.0.0:6032`, or `host:6032`, not a bare `6032`. Parsing it as a
    plain integer silently discarded every value the sidecar accepts, so accept all four
    forms and keep only the port.

    The host half is deliberately ignored: a listen address says what the sidecar binds, not
    where to reach it, and `0.0.0.0` is not a connect target. Use GREMLIN_SIDECAR_HOST to
    move the host.
    """
    global logger
    try:
        port = int(raw.rsplit(":", 1)[-1].strip())
    except ValueError:
        port = -1
    if port > 0 and port <= 65535:
        return port
    if debug:
        logger.debug(f"ignoring unusable {ENV_SIDECAR_PORT} value {raw!r}, using {DEFAULT_PORT}")
    return None

def resolveEndpoint(explicit, endpointVariable, hostVariable, portVariable, debug=False):
    """Resolves the sidecar URL, most specific source first: the `endpoint` argument, then
    FAILURE_FLAGS_ENDPOINT, then GREMLIN_SIDECAR_HOST and GREMLIN_SIDECAR_PORT (either may
    be set alone), then http://localhost:5032/experiment.

    A port that is not a number in 1..65535, and an endpoint that is not HTTP, fall back to
    the default rather than raising. This is a fail-safe library; bad configuration must not
    take the application with it.
    """
    global logger
    endpoint = cleanString(explicit) or cleanString(endpointVariable)
    if endpoint is not None:
        if endpoint.lower().startswith(ALLOWED_SCHEMES):
            return endpoint
        if debug:
            logger.debug(f"ignoring endpoint {endpoint!r}: only http and https are supported")
    host = cleanString(hostVariable) or DEFAULT_HOST
    port = DEFAULT_PORT
    raw = cleanString(portVariable)
    if raw is not None:
        parsed = parsePort(raw, debug)
        if parsed is not None:
            port = parsed
    return f"http://{host}:{port}/experiment"

def resolveTimeout(explicit, timeoutVariable):
    """Resolves the fetch deadline in seconds, most specific source first: the `timeout`
    argument (seconds), then FAILURE_FLAGS_TIMEOUT_MS (milliseconds, matching the other
    SDKs), then DEFAULT_TIMEOUT. Non-positive and unparsable values fall back.
    """
    if (type(explicit) is int or type(explicit) is float) and explicit > 0:
        return explicit
    raw = cleanString(timeoutVariable)
    if raw is not None:
        try:
            ms = float(raw)
            if ms > 0:
                return ms/1000
        except ValueError:
            pass # keep the default
    return DEFAULT_TIMEOUT

def isSelected(experiment, dice, debug=False):
    """True when `experiment` is well-formed and `dice` landed under its `rate`.

    An absent or null `rate` means 1.0, always apply, which is what the Go and Node SDKs do
    (Go declares the field and never reads it; Node only drops an experiment when `rate` is
    a valid number and the dice lose). Requiring one made a payload without a rate a silent
    no-op that still reported `active`, so Gremlin saw an experiment that injected nothing.

    A `rate` that is present but is not a number in [0,1] is malformed: skip it and say so,
    rather than guessing which direction the operator meant.

    Anything malformed is simply not selected. The sidecar response is not trusted input
    and `invoke()` promises never to raise on its own.
    """
    global logger
    if not isinstance(experiment, dict):
        if debug:
            logger.debug("experiment is not an object, not selected")
        return False
    rate = experiment.get("rate")
    if rate is None:
        rate = 1
    if (type(rate) is not int and type(rate) is not float) or not isfinite(rate):
        if debug:
            logger.debug(f"experiment rate {rate!r} is not a number, not selected")
        return False
    if rate < 0 or rate > 1:
        if debug:
            logger.debug(f"experiment rate {rate!r} is outside [0,1], not selected")
        return False
    return dice < rate

class FailureFlag:
    """FailureFlag represents a point in your code where you want to be able to inject failures dynamically.
    
    The FailureFlag object can be created anywhere and will only have an effect at the line where the 
    invoke() function is called. Instead of relying on the built-in behavior processing a user can call the
    fetch() function to simply retrieve any active experiments targeting a FailureFlag.

    This package is inert unless the FAILURE_FLAGS_ENABLED environment variable is set to
    `true`, `yes`, or `1`.

    This package sends debug logs to a logger named `failureflags`.
    """

    def __init__(self, name, labels, behavior=None, data=None, debug=False, timeout=None, endpoint=None):
        """Create a new FailureFlag.

        Keyword arguments:
        behavior -- a function to invoke for retrieved experiments instead of the default behavior chain.
        debug -- True or False (default False) to control debug logging.
        data -- Data to be mutated by behaviors and effect data.
        timeout -- the fetch deadline in seconds. Overrides FAILURE_FLAGS_TIMEOUT_MS. Note
                   the units: this argument is seconds, the environment variable is
                   milliseconds. Defaults to DEFAULT_TIMEOUT.
        endpoint -- the sidecar URL. Overrides FAILURE_FLAGS_ENDPOINT and
                    GREMLIN_SIDECAR_HOST/GREMLIN_SIDECAR_PORT.

        `timeout` and `endpoint` are stored as provided; None means "not specified" and
        leaves the environment in charge. Read the values actually used from
        `resolveTimeout` and `resolveEndpoint`.
        """
        
        self.name = name
        self.labels = labels
        self.behavior = behavior if behavior != None else defaultBehavior
        self.data = {} if data is None else data
        self.debug = True if debug != False else False # filter out any other possible values that might be provided
        self.timeout = timeout
        self.endpoint = endpoint

    @property
    def enabled(self):
        """True when FAILURE_FLAGS_ENABLED is set to `true`, `yes`, or `1` (case-insensitive).

        Read from the environment on each access, so a FailureFlag constructed at import
        time, before the process environment is fully configured, is not stuck with a
        stale answer.

        Read-only: through 1.0.3 this was a plain attribute, so assigning to it worked.
        Set the environment variable instead.
        """
        return isEnabled(os.environ.get(ENV_ENABLED))

    def __str__(self):
        return f"<FailureFlag name:{self.name} labels:{self.labels} debug:{self.debug}>"

    def invoke(self):
        """Invokes any experiments that may be running and target this FailureFlag.

        This function uses `fetch()` under the covers to retrieve any experiments targeting this
        FailureFlag, and orchestrates the application of probablistic impact and handoff to 
        either the configured custom behavior or the default behavior chain.

        Like `fetch()` calls to `invoke()` will shortcut any experiment lookup or application if
        the SDK has not been explicitly enabled by setting FAILURE_FLAGS_ENABLED to `true`,
        `yes`, or `1`.

        Unlike `fetch()` this function will never raise any Exception unless there is an active
        experiment configured to do so. 

        `invoke()` returns a triple: `active`, `impacted`, and `experiments`. In the first
        position, `active` is a boolean indicating if there was any active experiment targeting
        this FailureFlag. In second position, `impacted` is a boolean indicating if any of the
        configured behaviors were activated in processing active experiments. Last, 
        `experiments` is the list of active experiments targeting this FailureFlag. Use
        `experiments` to drive any externalized behavior handling you may have in branching
        logic.
        """
        global logger
        active = False
        impacted = False
        experiments = []
        if not self.enabled:
            if self.debug:
                logger.debug("SDK not enabled")
            return (active, impacted, experiments)
        if not isinstance(self.name, str) or len(self.name) == 0:
            # a name straight out of a dict .get() or a config lookup is an ordinary way to
            # arrive here holding None, and len(None) took down the request path this
            # library exists to make more reliable
            if self.debug:
                logger.debug(f"no usable failure flag name specified: {self.name!r}")
            return (active, impacted, experiments)
        try:
            experiments = self.fetch()
        except Exception as err:
            if self.debug:
                logger.debug(f"received error while fetching experiments, {err}")
            return (active, impacted, experiments)
        if len(experiments) > 0:
            active = True
            dice = random()
            selected = [e for e in experiments if isSelected(e, dice, self.debug)]
            if callable(self.behavior):
                # the behavior is allowed to raise: that is the injected fault
                impacted = self.behavior(self, selected)
            elif self.debug:
                logger.debug(f"configured behavior {self.behavior!r} is not callable, skipping")
        else:
            if self.debug:
                logger.debug("no experiments retrieved")
        return (active, impacted, experiments)

    def fetch(self):
        """`fetch()` requests the current set of active experiments for this FailureFlag.
        This function will raise exceptions if there is a problem communicating with the
        sidecar process. The response will always be a list.
        This function does not analyse the resulting list of experiments or apply
        probablistic pruning of the list.
        """
        global logger
        global VERSION
        experiments = []
        if not self.enabled:
            return experiments
        # annotate a copy: the labels dict belongs to the caller
        labels = {}
        if isinstance(self.labels, dict):
            labels = dict(self.labels)
        elif self.labels is not None and self.debug:
            logger.debug(f"labels {self.labels!r} is not a dict, sending none")
        labels["failure-flags-sdk-version"] = f"python-{VERSION}"
        data = json.dumps({"name": self.name, "labels": labels}).encode("utf-8")
        endpoint = resolveEndpoint(self.endpoint,
                                   os.environ.get(ENV_ENDPOINT),
                                   os.environ.get(ENV_SIDECAR_HOST),
                                   os.environ.get(ENV_SIDECAR_PORT),
                                   self.debug)
        timeout = resolveTimeout(self.timeout, os.environ.get(ENV_TIMEOUT_MS))
        request = Request(endpoint,
                          headers={"Content-Type": "application/json", "Content-Length": len(data)},
                          data=data)
        with urlopen(request, timeout=timeout) as response:
            code = response.status if hasattr(response, 'status') else 0
            if code < 200 or code >= 300:
                if self.debug:
                    logger.debug(f"bad status code ({code}) while fetching experiments")
                return []

            # No experiments is the normal case and the sidecar says so with a bare 204,
            # no Content-Type and no Content-Length. Answer it before the header checks
            # below, which would otherwise log a scary line on every single call.
            if code == 204:
                if self.debug:
                    logger.debug("no experiments (204 No Content)")
                return []

            # Validate Content-Type. Compare the media type only: `application/json;
            # charset=utf-8` is legal and common, and matching the whole header exactly
            # meant one proxy adding a parameter would silence the SDK fleet-wide.
            content_type = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
            if content_type != "application/json":
                if self.debug:
                    logger.debug(f"unexpected Content-Type: {content_type}")
                return []

            # Validate Content-Length
            content_length = response.headers.get("Content-Length", None)
            if content_length is None or not content_length.isdigit() or int(content_length) <= 0:
                if self.debug:
                    logger.debug(f"invalid Content-Length: {content_length}")
                return []

            # Read the response body
            body = response.read().decode('utf-8').strip()  # Decode and strip whitespace
            response.close()
            if len(body) == 0:
                # a positive Content-Length with a whitespace-only body reached
                # json.loads("") and raised out of the public fetch()
                if self.debug:
                    logger.debug("empty response body")
                return []
            experiments = json.loads(body)
            if isinstance(experiments, list):
                return experiments
            elif isinstance(experiments, dict):
                return [experiments]
            else:
                return []

def delayedDataOrError(failureflag, experiments):
    """`delayedDataOrError()` is the head of the default behavior chain used by `invoke()`.

    This chain will process `latency` effects, then `exception` effects, and finally
    `data` effects. The `data` effects are not yet implemented. This function will 
    return True if any of the three effects in the chain return True.
    """
    latencyImpact = latency(failureflag, experiments)
    exceptionImpact = exception(failureflag, experiments)
    dataImpact = data(failureflag, experiments)
    return latencyImpact or exceptionImpact or dataImpact

def asMilliseconds(value):
    """Returns `value` as a non-negative float of milliseconds, or None if it is not a
    usable number.

    JSON has a single number type, so an effect the control plane serialises as `1000`
    arrives as an int and `1000.0` arrives as a float. Accepting only int made a float
    latency a silent no-op, and made a float `ms` inside a latency object report impact
    while sleeping zero. Both are numbers; treat them alike, as Node does with `typeof
    latency === "number"`.

    Strings are accepted because the effect editor allows them. Booleans are not numbers
    here. NaN and infinity are rejected outright: `time.sleep(inf)` hangs the caller
    forever, which is the one thing this library must never do. Negatives clamp to zero so
    a nonsensical value is no impact rather than a ValueError out of time.sleep().
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        ms = float(value)
    elif isinstance(value, str):
        try:
            ms = float(value)
        except ValueError:
            return None
    else:
        return None
    if not isfinite(ms):
        return None
    return ms if ms > 0 else 0.0

def latency(ff, experiments):
    """`latency` processes `latency` clauses in effect statements for each provided experiment in the list."""
    impacted = False
    # the latency effect should never cause an Exception to be thrown even if the SDK has a bug.
    try:
        if experiments == None or len(experiments) == 0:
            if ff.debug:
                logger.debug("experiments was empty")
            return impacted
        for e in experiments:
            if not isinstance(e, dict):
                if ff.debug:
                    logger.debug("experiment is not a dict, skipping")
                continue
            if "effect" not in e or not isinstance(e["effect"], dict):
                if ff.debug:
                    logger.debug("no effect in experiment, skipping")
                continue
            if "latency" not in e["effect"]:
                if ff.debug:
                    logger.debug("no latency in experiment effect, skipping")
                continue
            clause = e["effect"]["latency"]
            if isinstance(clause, dict):
                ms = asMilliseconds(clause.get("ms"))
                jitter = asMilliseconds(clause.get("jitter"))
                if ms is None and jitter is None:
                    if ff.debug:
                        logger.debug(f"latency clause {clause!r} carries no usable delay, skipping")
                    continue
                delay = (ms or 0) + (jitter or 0)*random()
            else:
                delay = asMilliseconds(clause)
                if delay is None:
                    if ff.debug:
                        logger.debug(f"experiment contained a non-number latency clause: {clause!r}")
                    continue
            if delay <= 0:
                # claiming impact for a clause that resolves to no delay reports a fault
                # to Gremlin that the application never felt
                if ff.debug:
                    logger.debug(f"latency clause {clause!r} resolved to {delay}ms, skipping")
                continue
            impacted = True
            time.sleep(delay/1000)
    except Exception as oerr:
        if ff.debug:
            logger.debug(f"experiments caused an exception to be thrown in latency, {oerr}")
    return impacted

def loadException(module, class_name, message, debug=False):
    """Builds the Exception named by `module` and `class_name` with `message` as its sole
    argument, falling back to a ValueError carrying `message` when that name cannot be
    resolved.

    This never returns None on purpose. An experiment that cannot load its class must
    still raise something, or Gremlin reports impact while the application saw nothing at
    all.
    """
    global logger
    module_name = module if module is not None else "builtins"
    try:
        module_ = __import__(module_name, fromlist=[class_name])
        error = getattr(module_, class_name)(message)
        if not isinstance(error, BaseException):
            # `raise` would throw a TypeError of our own making from the caller's line
            raise TypeError(f"{module_name}.{class_name} is not an exception type")
        return error
    except Exception as err:
        if debug:
            logger.debug(f"unable to load {module_name}.{class_name}, falling back to ValueError, {err}")
        return ValueError(message)

def exception(ff, experiments):
    """`exception` processes `exception` clauses in effect statements for each provided experiment in the list.

    `exception` clauses may be simple strings, or dictionaries. If an experiment provides
    a simple string then this function will raise a `ValueError` and use the string as the
    message. If the experiment specified a dict then this function will look for four
    keys: `module`, `className`, `name`, and `message`. If `module` is provided then this 
    function will attempt to import that module, and get a reference to the item in that 
    module with the name provided in `className` (or `name`, its cross-language alias;
    `className` wins when both are present). If `module` is not provided then this 
    function attempts to load the class from `builtins`. If the class cannot be loaded
    then a `ValueError` is raised instead. This function always provides the value for
    `message` as the sole argument when invoking the function identified by `className`.
    """
    global logger
    for f in experiments:
        if not isinstance(f, dict):
            continue
        if "effect" not in f or not isinstance(f["effect"], dict):
            continue
        if "exception" not in f["effect"]:
            continue
        if type(f["effect"]["exception"]) is str:
            # this is the feature
            raise ValueError(f["effect"]["exception"])
        elif isinstance(f["effect"]["exception"], dict):
            clause = f["effect"]["exception"]
            module = None
            class_name = None
            message = "Error injected via Gremlin Failure Flags (default message)"
            hasKnown = False
            if type(clause.get("module")) is str:
                module = clause["module"]
                hasKnown = True
            # `name` is the documented cross-language key for the exception type and
            # `className` is the Python-specific alias, so `className` wins when both
            # are present.
            for key in ("name", "className"):
                if type(clause.get(key)) is str:
                    class_name = clause[key]
                    hasKnown = True
            if type(clause.get("message")) is str:
                message = clause["message"]
                hasKnown = True
            if not hasKnown:
                if ff.debug:
                    logger.debug("exception clause was not populated")
                continue
            if class_name is not None and len(class_name) == 0:
                # for some reason this was explicitly unset
                continue
            # this is the acceptable place to raise an exception
            raise loadException(module, class_name if class_name is not None else "ValueError", message, ff.debug)
    return False

def data(ff, experiments):
    """data is not yet implemented"""
    if ff.debug:
        logger.debug("data effects are not yet implemented")
    return False

defaultBehavior = delayedDataOrError
