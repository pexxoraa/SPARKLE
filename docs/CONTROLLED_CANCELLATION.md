# Controlled execution cancellation

Controlled execution remains parked for Level 3 manual acceptance, but the software-side cancellation path now covers queued and running work.

Queued/requested/authorized executions retain the existing local cancellation transition. A RUNNING execution sends a separate signed cancellation request to the configured worker using `SPARKLE-WORKER-CANCEL/1`. The request identifies the controlled `execution_id`, not model-provided content. The worker authenticates the request with the same timestamp/HMAC boundary as job submission and only exposes `/v1/jobs/cancel`.

The cancellable worker registers an event for each controlled execution before starting the fixed child process. Its executor polls the event and kills the child process group when cancellation is requested. The controller then atomically records `cancelled` with `OperatorCancelled`; cancellation is terminal and appended to lifecycle evidence. A concurrent original request reconciles to that durable cancelled state if response processing loses the race.

The default `sparkle-worker` entry point now uses the cancellation-aware worker service. Existing submission schemas and result verification remain unchanged. Real host/process cancellation, TLS termination behavior and Level 3 isolation acceptance remain externally pending; this implementation does not unpark Level 3 or deployment.
