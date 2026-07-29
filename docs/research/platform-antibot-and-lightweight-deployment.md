# Platform Anti-Bot and Lightweight Deployment Research

Date: 2026-07-29

Status: `initial_research`

Purpose: record realistic capture routes and dependency-light alternatives for
OKS. This is not a bypass plan. OKS should preserve evidence and failure states,
not defeat platform access controls.

## Summary

The recommended OKS strategy is:

1. Use official APIs when the platform exposes the needed data.
2. Use OAuth/user authorization when private user data is required.
3. Use browser snapshots only for user-visible pages and preserve the snapshot
   as evidence.
4. Use mature tools such as `yt-dlp` only within their documented and legal use
   boundaries.
5. Prefer remote OCR/ASR/document APIs for heavy optional capabilities when the
   user accepts cost and data-transfer tradeoffs.
6. Keep local extractors optional and isolated; never install every modality for
   the first text POC.

## Route Matrix

| Source type | Recommended route | OKS status semantics |
|---|---|---|
| Public text/Markdown | Direct download or saved local file -> document ingest | `passed` if hash and Raw validate |
| Ordinary public web page | Fetch receipt/browser snapshot -> local ingest | `passed` or `partial` depending locator quality |
| Script-rendered page | Browser snapshot with user-visible DOM and screenshot | `partial` unless stable content and provenance are preserved |
| YouTube metadata | YouTube Data API where quota and permissions allow | `passed` only for API-covered fields |
| YouTube captions/video | Official API where available; otherwise mature tool with user-provided access, cookies only when user authorized | anti-bot/login failures are `environment_limited` or `platform_limited` |
| Bilibili public video | Official Open Platform where available; otherwise user-authorized browser/tool route | do not claim universal capture |
| PDF | Local PDF file -> PDF/document extractor | `passed` if extractor binary and models are available |
| Login-only/paid/DRM content | OAuth/API/export provided by user | do not bypass; mark `restricted` if no legal route |

## Source Notes

- YouTube Data API documentation exposes API resources and quota-cost rules;
  this supports metadata/API-backed workflows but does not imply unrestricted
  video scraping.
- YouTube API Services policies govern API use and should be treated as a hard
  boundary for automated capture.
- `yt-dlp` is a mature third-party downloader with documented site support and
  cookie/browser-session options, but its success can vary with platform
  countermeasures and user authorization.
- Bilibili has an official open platform. OKS should prefer documented APIs
  where they cover the task and record when a requested field is unavailable.
- Model APIs can reduce local dependency weight for OCR, ASR, vision, and
  summarization, but they introduce cost, privacy, latency, provider limits, and
  provenance requirements.

## Dependency Weight Guidance

| Capability | Local dependency cost | Lightweight alternative | Recommendation |
|---|---:|---|---|
| text/Markdown/document | low to medium | MarkItDown or plain parser | keep as first POC path |
| PDF layout | medium to high | cloud document parsing API | optional; install only for PDF tests |
| formula OCR | high | remote OCR/vision model API | optional; expose through explicit CLI before claiming capability |
| video/audio | high | official captions API, remote ASR, user-provided transcript | optional; record `ffprobe`/model/platform failures honestly |
| image OCR | medium | remote OCR/vision model API | task-dependent |
| Feishu | low local dependency, high admin/config dependency | runtime credentials and dedicated Base | optional control plane only |

## Recommended OKS Implementation Boundary

OKS should own:

- route planning;
- capability installation hints;
- Raw Bundle evidence;
- Candidate/Wiki/review lifecycle;
- recall and evaluation reports.

OKS should not own:

- platform anti-bot bypass;
- DRM circumvention;
- paid-wall access;
- a new downloader ecosystem;
- a local copy of every heavy model.

## Practical Next Step

Add capability reports that state:

- required system binaries;
- Python packages and install size;
- whether a cloud/API alternative exists;
- privacy implications;
- legal/platform restrictions;
- exact failure classification.

This keeps OKS usable while allowing power users to add heavier extractors when
the task actually needs them.

## References

- YouTube Data API documentation: https://developers.google.com/youtube/v3
- YouTube Data API quota costs: https://developers.google.com/youtube/v3/determine_quota_cost
- YouTube API Services Terms and Policies: https://developers.google.com/youtube/terms/developer-policies
- yt-dlp project documentation: https://github.com/yt-dlp/yt-dlp
- Bilibili Open Platform: https://openhome.bilibili.com/
- Moonshot/Kimi developer documentation: https://platform.moonshot.ai/docs
