# Data flow and tracing

```mermaid
sequenceDiagram
    participant U as User interface
    participant O as Orchestrator
    participant C as Context stores
    participant M as Model adapter
    participant T as Tool registry
    participant R as Trace store
    U->>O: Request
    O->>C: Relevant context
    O->>M: Provider-neutral request
    M-->>O: Text or tool calls
    O->>T: Allowed tool call
    T-->>O: Result
    O->>R: Outcome metadata
    O-->>U: Verified response
```

Every run records trace ID, source, agent, model, provider, tools, data stores
accessed, transformations, destinations, status, safe result summary, error
type, timestamps, and duration. Traces exclude authorization headers, request
bodies, provider thinking blocks, and secret values.
