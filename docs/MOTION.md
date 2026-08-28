# Motion and presence

`PresenceEngine` is an embodiment-neutral state machine with idle, working, and
error modes plus activity, agent, trace, and update time. The dashboard can
animate this state without coupling intelligence to its appearance.

Camera perception, gesture, spatial state, robot protocols, safety controllers,
and physical motion are not implemented. Any future physical adapter must sit
below a permissioned motion interface with independent safety interlocks.
