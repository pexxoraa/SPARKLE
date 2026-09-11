# Presence and motion software boundary

SPARKLE presence is now durable across process restarts. The current mode, activity, agent and trace linkage are stored under `SPARKLE_DATA_DIR/data_environment/presence.sqlite3`, with a bounded history for dashboard/diagnostic use.

Presence modes are validated (`idle`, `listening`, `thinking`, `working`, `speaking`, `error`, `offline`). History retains at most 10,000 transitions.

Physical motion is represented by a provider-neutral `MotionAdapter` and typed `MotionCommand`. The default adapter exposes no capabilities and fails closed. A configured adapter must explicitly declare supported command kinds; execution requires explicit operator approval and stores bounded event evidence. Motion events never imply hardware acceptance: returned records keep `hardware_verified=false` until separate human/device validation exists.

This completes the software-side persistence, permission, adapter and evidence boundary. Actual motors, sensors, robotics middleware and physical safety acceptance remain external/hardware-dependent.
