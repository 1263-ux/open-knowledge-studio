# Feishu E2E Status

Date: 2026-07-29

Status: `partial`

This page corrects the acceptance language for Feishu. Feishu is an optional
private control plane for capture, status, and review. It is not required for
the non-Feishu OKS CLI loop.

## Current Truth Table

| Assertion | Status | Meaning |
|---|---|---|
| `api_form_submission_to_raw` | `passed` | API-created records can enter the Worker path and reach Raw/Candidate. |
| `public_form_human_submission` | `not_run` | A human opening the public form and submitting URL/attachment has not been proven in the recorded run. |
| `candidate_private_message_notification` | `passed` | Candidate review notification can be sent to the reviewer. |
| `review_consumer_startup` | `passed` | The event consumer can start and expose a ready state. |
| `review_websocket_connected` | `passed` | WebSocket connection was observed. |
| `native_review_event_delivery` | `failed` | No native review event was delivered during the recorded bounded window. |
| `reconcile_review_recovery` | `passed` | Recovery can reconcile missed review state. |
| `feishu_e2e` | `partial` | The full real-time event chain is not proven. |

## Boundary

Capture and review are separate paths:

- Capture path: public form -> Base record -> Worker -> extractor -> Raw ->
  Candidate.
- Review path: Candidate private message -> user approval -> Feishu
  `im.message.receive_v1` event -> Worker association -> Wiki promotion.

`im.message.receive_v1` is unrelated to public form capture. An Agent can start
and supervise a listener process, but it cannot replace Feishu administrator
configuration in the developer console. WebSocket connection is not the same as
event delivery.

`reconcile-review` remains useful for network loss, process restart, or missed
events. A flow that only succeeds through reconcile must remain `partial`, not
`passed`.

## Next Valid Feishu Test

The next Feishu acceptance test must use a dedicated test Base and runtime
credentials only. It should prove:

1. A human opens the public form.
2. The human submits a URL or attachment.
3. The Worker claims the record.
4. Only the needed extractor is installed.
5. Raw and Candidate are generated.
6. The user replies with an explicit approval.
7. The native real-time event delivers without manually supplying a message id.
8. Wiki promotion, search, recall, and lint complete.

Until all eight assertions pass, Feishu remains `partial`.
