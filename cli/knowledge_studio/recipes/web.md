# Recipe: Web

source_type: web
description: Public web pages, articles, documentation. Chinese platforms treated separately.

required_capabilities:
  - web.fetch
  - web.extract

optional_capabilities:
  - web.screenshot
  - metadata.fetch
  - image.observe
  - evidence.cross_check

complete_when:
  - main_article_text_extracted
  - title_and_metadata_available
  - challenge_or_paywall_status_recorded

remote_processing:
  policy_required: true

degradation:
  primary:
    capability: web.fetch
    providers: [http-fetch, firecrawl, agentkey]
  fallback:
    - capability: web.extract
      providers: [trafilatura, firecrawl, agentkey]
      condition: html_acquired
    - capability: web.screenshot
      providers: [firecrawl, browser]
      condition: js_rendering_required
    - capability: image.observe
      providers: [agent-runtime]
      condition: screenshot_available
    - capability: human.supply
      providers: [human]
      condition: challenge_or_auth_required

notes: |
  Public web pages: trafilatura for HTML article extraction (local, free).
  Firecrawl for JS-rendered pages and structured extraction (1 credit/call).
  Chinese platforms (zhihu, wechat, bilibili): agentkey is primary provider
  with platform-specific API access. Browser (Chrome CDP) for authenticated
  sessions. AgentKey maturity varies by platform — check provider.yaml.
  Firecrawl ineffective against Chinese anti-bot (CSDN, Juejin, Zhihu all fail).
