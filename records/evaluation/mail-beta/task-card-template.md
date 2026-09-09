# Mail Beta Task Card

复制本模板为 `YYYY-MM-DD-<task-id>.md`。任务卡只写必要的、可公开复现的任务信息，
不要写个人知识库正文、凭据或完整宿主日志。

## Task

- `task_id`:
- `date`:
- `task_kind`: code-change | code-review | research | test | conflict | resume
- `route`: claude-to-codex | codex-to-claude | human-to-agent
- `sender_host`:
- `receiver_host`:
- `real_task_summary`:
- `success_criterion`:
- `related_files_or_commit`:

## Mail and Session

- `thread_id`:
- `handoff_message_id`:
- `receiver_session_id`:
- `handoff_at`:
- `first_action_at`:
- `result_at`:
- `delivery_policy`: next_prompt | wait | notify
- `notification_result`: not_requested | queued | unsupported | presented

## Result

- `outcome`: pass | partial | fail | blocked
- `result_evidence`:
- `context_reask_count`:
- `human_intervention_count`:
- `duplicate_work_count`:
- `handoff_to_action_latency`:
- `unresolved_thread_count`:
- `failure_tags`:
- `primary_failure_cause`:

## Notes

- `what_the_receiver_already_had`:
- `what_was_still_missing`:
- `host_limitation_or_operator_action`:
- `follow_up_decision`: none | repeat | plan-change | owner-decision

