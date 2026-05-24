APPROVED

The Agent Lab BYO AI campaign delivered its stated MVP. The docs define the bring-your-own-AI trust boundary, user-mediated adapter contract, strict proposal schema, OAuth deferral, blocked-by-default actions, approval boundaries, audit records, and scanner-evidence distinction.

The backend now builds bounded Agent Lab context exports, validates hostile proposal imports, stores proposal and approval records, previews approved routes, and queues approved work through the existing DëvSec scan pipeline only. It blocks arbitrary commands, runnable packs, External Surface execution, provider OAuth, install/uninstall requests, unknown IDs, blocked tools, malformed list fields, and unsupported scan profiles. Missing or unavailable tools remain evidence gaps instead of silent success.

The dashboard exposes the user-mediated loop with Codex, Claude Code, local-agent, and manual JSON choices, context export, untrusted-import warnings, proposal review, safety labels, approval controls, dry-run route preview, queueing for approved scans, and audit history. Live provider/OAuth states remain visibly deferred.

Focused tests cover context export, pasted proposal import, schema/version failures, size-limit failure, unknown tools, External Surface rejection, runnable-pack rejection, arbitrary-command rejection, malformed list fields, omitted `tool_ids` defaults, approval/denial gates, missing-tool evidence gaps, markdown-wrapped import rejection, and approved execution through the existing scan pipeline.

Verification passed:

- `python3 -c "import sys; sys.path.insert(0, 'src'); import security_observatory.cli; print('ok')"` -> ok
- `uv run pytest` -> 187 passed
- `cd dashboard-ui && npm run lint` -> passed
- `make dashboard-build` -> passed
