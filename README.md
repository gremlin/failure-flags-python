# failure-flags

Failure Flags is a python SDK for building application-level chaos experiments and reliability tests using the Gremlin Fault Injection platform. This library works in concert with Gremlin-Lambda, a Lambda Extension; or Gremlin-Sidecar, a container sidecar agent. This architecture minimizes the impact to your application code, simplifies configuration, and makes adoption painless.

Just like feature flags, Failure Flags are safe to add to and leave in your application. Failure Flags will always fail safe if it cannot communicate with its sidecar or its sidecar is misconfigured.

Take three steps to run an application-level experiment with Failure Flags:

1. Instrument your code with this SDK
2. Configure and deploy your code along side one of the Failure Flag sidecars
3. Run an Experiment with the console, API, or command line

## Instrumenting Your Code

You can get started by adding failureflags to your package dependencies:

```sh
pip install failureflags
```

Then instrument the part of your application where you want to inject faults. 

```python
from failureflags import FailureFlag

...

FailureFlag(name: 'flagname', labels: {}).invoke()

...
```

The best spots to add a failure flag are just before or just after a call to one of your network dependencies like a database or other network service. Or you can instrument your request handler and affect the way your application responses to its callers. Here's a simple Lambda example:

```python
# Change 1: Bring in the failureflags module
from failureflags import FailureFlag

import os
import logging
import time
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all

logger = logging.getLogger()
logger.setLevel(logging.INFO)
patch_all()

def lambda_handler(event, context):
    start = time.time()

    # Change 2: add a FailureFlag to your code
    FailureFlag("http-ingress", {}, debug=True).invoke()

    end = time.time()
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json'
        },
        'body': {
            'processingTime': f"{start - end}",
            'isActive': active,
            'isImpacted': impacted
        }
    }
```

## Enabling the SDK in your Environment

*Don't forget to enable the SDK by setting the FAILURE_FLAGS_ENABLED environment variable!* If this environment variable is not set then the SDK will short-circuit and no attempt to fetch experiments will be made.

## Extensibility

You can always bring your own behaviors and effects by providing a behavior function. Here's another Lambda example that writes the experiment data to the console instead of changing the application behavior:

```python
# Change 1: Bring in the failureflags module
from failureflags import FailureFlag, defaultBehavior

import os
import logging
import time
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all

logger = logging.getLogger()
logger.setLevel(logging.INFO)
patch_all()

def customBehavior(ff, experiments):
    logger.debug(experiments)
    return defaultBehavior(ff, experiments)

def lambda_handler(event, context):
    start = time.time()

    # Change 2: add a FailureFlag to your code
    FailureFlag("http-ingress", {}, debug=True, behavior=customBehavior, timeout=.005).invoke()

    end = time.time()
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json'
        },
        'body': {
            'processingTime': f"{start - end}",
            'isActive': active,
            'isImpacted': impacted
        }
    }
```

### Providing Metadata to Custom Behaviors

The default effect chain included with the Failure Flags SDK is aware of well-known effect properties including, "latency" and "exception." The user can extend or replace that functionality and use the same properties, or provide their own. For example, suppose a user wants to use a "random jitter" effect that the Standard Chain does not provide. Suppose they wanted to inject a random amount of jitter up to some maximum. They could implement that small extension and make up their own Effect property called, "my-jitter" that specifies that maximum. The resulting Effect Statement would look like:

```json
{ "my-jitter": 500 }
```

They might also combine this with parts of the default chain:

```json
{
  "latency": 1000,
  "my-jitter": 500
}
```

## Alternatively, use it like a Feature Flag

Sometimes you need even more manual control. For example, in the event of an experiment you might not want to make some API call or need to rollback some transaction. In most cases the Exception effect can help, but the `invoke` function also returns a boolean to indicate if there was an experiment. You can use that to create branches in your code like you would for any feature flag.

```python
...
active, impacted, experiments = FailureFlag("myFlag", {}).invoke()
if active and impacted:
  // if there is a running experiment then do this
else:
  // if there is no experiment then do this
...
```

### Pulling the Experiment and Branching Manually

If you want to work with lower-level Experiment data you can use `fetch` directly.

## Building Experiments: Targeting with Selectors

Experiments match specific invocations of a Failure Flag based on its name, and the labels you provide. Experiments define Selectors that the Failure Flags engine uses to determine if an invocation matches. Selectors are simple key to list of values maps. The basic matching logic is every key in a selector must be present in the Failure Flag labels, and at least one of the values in the list for a selector key must match the value in the label.

## Effects and Examples

Once you've instrumented your code and deployed your application with the sidecar you're ready to run an Experiment. None of the work you've done so far describes the Effect during an experiment. You've only marked the spots in code where you want the opportunity to experiment. Gremlin Failure Flags Experiments take an Effect parameter. The Effect parameter is a simple JSON map. That map is provided to the Failure Flags SDK if the application is targeted by a running Experiment. The Failure Flags SDK will process the map according to the default behavior chain or the behaviors you've provided. Today the default chain provides both latency and error Effects.

### Introduce Flat Latency

This Effect will introduce a constant 2000 millisecond delay.

```json
{ "latency": 2000 }
```

### Introduce Minimum Latency with Some Maximum Jitter

This Effect will introduce between 2000 and 2200 milliseconds of latency where there is a pseudo-random uniform probability of any delay between 2000 and 2200.

```json
{
  "latency": {
    "ms": 2000,
    "jitter": 200
  }
}
```

### Throw an Error

This Effect will cause Failure Flags to throw a ValueError with the provided message. This is useful if your application uses Errors with well-known messages.

```json
{ "exception": "this is a custom message" }
```

If your app uses custom error types or other error condition metadata then use the object form of exception. This Effect will cause the SDK to import http.client module and raise an http.client.ImproperConnectionState exception:

```json
{
  "exception": {
    "message": "this is a custom message",
    "module": "http.client",
    "className": "ImproperConnectionState"
  }
}
```

If `module` is omitted the SDK will assume `builtins`. If `className` is omitted the SDK will assume `ValueError`.

### Combining the Two for a "Delayed Exception"

Many common failure modes eventually result in an exception being thrown, but there will be some delay before that happens. Examples include network connection failures, or degradation, or other timeout-based issues.

This Effect Statement will cause a Failure Flag to pause for a full 2 seconds before throwing an exception/error a message, "Custom TCP Timeout Simulation"

```json
{
  "latency": 2000,
  "exception": {
    "message": "Custom TCP Timeout Simulation",
    "className": "TimeoutError"
  }
}
```

