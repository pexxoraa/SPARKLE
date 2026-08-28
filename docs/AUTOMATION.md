# Automation and proactive intelligence

The automation store supports once, daily, weekly, and conditional records with
actions, schedule metadata, next-run time, enabled state, and last-run state.
`due()` selects scheduled work deterministically.

The proactive engine currently detects overdue and approaching deadlines from
task, exam, project, and goal memory metadata. It does not invent alerts when no
deadline data exists.

A continuously running scheduler, notification delivery, calendar connector,
and external event webhooks are not yet packaged.
