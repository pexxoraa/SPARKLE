# Application Builder

The Application Builder is implemented as a specialized agent routed to a
coding-capable model and allowed safe file/context tools. Its instruction covers
requirements, UX, architecture, implementation, tests, packaging, and
deployment.

Current limitation: SPARKLE cannot yet create an isolated child workspace or
execute arbitrary build commands through its own API. The hosting build agent
can do that, but it is not packaged as a runtime capability. A future workspace
manager and permissioned development runner must be added before autonomous
application delivery can be marked complete.
