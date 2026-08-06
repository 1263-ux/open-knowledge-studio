# Recipe: Video

source_type: video
description: Platform videos (Bilibili, YouTube, Douyin) and local video files.

required_capabilities:
  - subtitle.fetch
  - metadata.fetch

optional_capabilities:
  - media.download
  - media.probe
  - audio.extract
  - video.keyframes
  - speech.transcribe
  - image.observe
  - chart.interpret
  - layout.understand

complete_when:
  - subtitles_or_transcript_available
  - metadata_title_and_duration_recorded
  - keyframes_extracted_if_visual_content_significant

remote_processing:
  policy_required: true

degradation:
  primary:
    capability: subtitle.fetch
    providers: [yt-dlp, agentkey]
  fallback:
    - capability: metadata.fetch
      providers: [yt-dlp, agentkey]
      condition: subtitle_unavailable
    - capability: audio.extract
      providers: [ffmpeg]
      condition: local_media_available
    - capability: speech.transcribe
      providers: [local-asr, remote-asr]
      condition: audio_track_available
    - capability: video.keyframes
      providers: [ffmpeg]
      condition: visual_content_significant
    - capability: image.observe
      providers: [agent-runtime]
      condition: keyframes_available
    - capability: human.supply
      providers: [human]
      condition: all_automated_failed

notes: |
  Bilibili: yt-dlp with Cookie (7/10 verified). AgentKey API returns metadata
  (title, BV, aid/cid) but NO subtitle body — metadata_only, not text success.
  YouTube: blocked in PRC network environment. Douyin: not yet tested.
  Local video: ffmpeg extracts audio and keyframes. Agent-runtime understands
  visual content from keyframes. ASR generates transcript from audio.
  Without video files or keyframes, content is limited to subtitles + metadata.
  Video capability is the most complex — last to fully automate.
