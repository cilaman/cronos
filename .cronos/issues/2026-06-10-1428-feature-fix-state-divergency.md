# FIX-002: Feature / fix state divergency

Feature / Fix state is divergent from Tasks, that realise the feature / fix.

States:
- Backlog - feature created 
- Processing 
-- Tasks and Goals for the Feature or fix are being created OR
-- Tasks and Goals are in Active state
- Planned - Tasks and Goals are created and in Backlog
- Waiting - Tasks and Goals are in Waiting state
- Done - Tasks and Goals for the Feature or fix are either DONE or Archived

The order of the Feature lanes should be
- Backlog, Planned, Processing, Waiting, Done
