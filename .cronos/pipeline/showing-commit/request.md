Show, in the GUI sidebar next to the CRONOS text in the top-left corner, the git commit that is currently running, so the operator can see at a glance whether the deployed app is in sync with current main.

It would also be valuable to show a timestamp of when the GUI and the backend were last upgraded.

Notes / acceptance:
- The running commit must reflect what is actually deployed (baked at build/upgrade time), not a value read from a working tree.
- Ideally the commit is comparable against origin/main (e.g. a short SHA, optionally linking to the commit on GitHub).
- Surface upgrade/build timestamps for both the frontend (GUI) and backend.
- The deployed app is rebuilt from origin/main by upgrade.sh, so any build-stamp wiring must flow through the upgrade + docker build path.
