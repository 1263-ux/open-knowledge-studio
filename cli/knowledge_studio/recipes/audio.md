# Recipe: Audio

source_type: audio
description: Local audio files (MP3, WAV, M4A, etc.).

required_capabilities:
  - speech.transcribe

optional_capabilities:
  - media.probe
  - metadata.fetch
  - evidence.cross_check

complete_when:
  - full_transcript_available
  - duration_and_format_recorded

remote_processing:
  policy_required: true

degradation:
  primary:
    capability: speech.transcribe
    providers: [local-asr, remote-asr]
  fallback:
    - capability: media.probe
      providers: [ffmpeg]
      condition: metadata_needed
    - capability: human.supply
      providers: [human]
      condition: asr_unavailable_or_failed

notes: |
  Local ASR: faster-whisper via watch capability (verified on 12s short clip,
  longer audio blocked by network in test environment).
  Remote ASR: OpenAI Whisper API or Groq (requires API key + user policy).
  12s short audio verified; longer audio not yet accepted in current environment.
