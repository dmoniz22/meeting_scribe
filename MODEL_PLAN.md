# MODEL_PLAN.md — Meeting Transcriber

## Central Policy Reference
See the canonical model strategy at:
`/home/dmoniz/.openclaw/workspace-coding/MODEL_PLAN.md`

## Per-Repo Defaults
- **Primary model:** `openrouter/qwen/qwen3.5-35b-a3b`
- **Fallbacks (in order):**
  1. `openrouter/minimax-m2`
  2. `openrouter/kimi-k2.5`
  3. `openrouter/mimi-v2`
- **Switching policy:** priority (prefer primary; fallback if unavailable)

## Project-Specific Notes
- Transcription uses local Whisper (not affected by this model plan)
- Summarization can use local Ollama or OpenRouter — this plan governs the OpenRouter choice
- For heavy audio pipeline debugging, consider upgrading to Claude Sonnet 4.5 temporarily

## How to Update
1. Edit this file with new primary/fallback choices
2. Commit and push
3. Central policy remains unchanged unless you also update the workspace MODEL_PLAN.md
