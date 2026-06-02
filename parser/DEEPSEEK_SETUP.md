# DeepSeek V4 Integration Guide

## Overview

This parser now supports DeepSeek V4 Flash as an alternative LLM provider through OpenRouter API, alongside Gemini 2.5 Flash and Groq Llama-3.3 70B.

## Setup

### 1. Get OpenRouter API Key

1. Visit https://openrouter.ai/keys
2. Create or copy your API key
3. Add to your `.env` file:

```bash
DEEPSEEK_API_KEY=your-openrouter-api-key
```

### 2. Update Dependencies

The `openai>=1.0,<2.0` SDK is already listed in `pyproject.toml`. Install it:

```bash
pip install -e .
```

### 3. Configure (Optional)

Add to `.env` to set DeepSeek as default:

```bash
LLM_PROVIDER=deepseek
DEEPSEEK_MODEL=deepseek/deepseek-v4-flash  # default
```

Or override per model version:

```bash
DEEPSEEK_MODEL=deepseek/deepseek-v4  # use full version instead of Flash
```

## Usage

### Via CLI Flag

Run a single parse with DeepSeek (Gemini/Groq stay as fallback):

```bash
python -m parser.cli run --city perm --provider deepseek --dry-run
```

### Via Environment Variable

Set default provider:

```bash
export LLM_PROVIDER=deepseek
python -m parser.cli run --city perm --dry-run
```

### Local Development

Optional: Add a test source to `parser/config/seeds.yaml` for easy testing:

```yaml
# Uncomment to enable for local testing
- name: quizplease-deepseek-test
  kind: listing
  url: https://perm.quizplease.ru/schedule
  extraction_mode: batch_listing
  provider: deepseek
```

Then run:

```bash
python -m parser.cli run --city perm --source quizplease-deepseek-test --dry-run
```

## API Details

- **Provider:** OpenRouter (https://openrouter.ai/api/v1)
- **Model ID:** `deepseek/deepseek-v4-flash`
- **API Key Format:** OpenRouter API key
- **Context Window:** 32K (sufficient for batch extraction)
- **Rate Limits:** Free tier available; check OpenRouter dashboard for details

## Troubleshooting

### Error: "DEEPSEEK_API_KEY не задан"

Make sure `DEEPSEEK_API_KEY` is in your `.env` file and `--provider deepseek` is set.

### Error: "DeepSeek API error"

Check:
1. API key is valid (test at https://openrouter.ai/keys)
2. OpenRouter service is reachable
3. Account has remaining credits
4. Model ID is correct (`deepseek/deepseek-v4-flash`)

### Response Format Issues

DeepSeek follows OpenAI-compatible API. If response validation fails:
1. Check logs for actual JSON response
2. Verify Pydantic schema matches response structure
3. Report issue with example response

## Performance Comparison

Expected metrics (vs. Gemini/Groq):

- **Speed:** Fast (optimized Flash variant)
- **Cost:** Low (free tier available via OpenRouter)
- **Quality:** Similar or better for structured extraction
- **Token Usage:** ~5-8k tokens per batch extraction (Perm QuizPlease)

## Notes

- DeepSeek is opt-in; existing Gemini/Groq configurations unaffected
- Supports both `extract()` (single event) and `extract_many()` (batch) modes
- System prompts are identical to Groq—schema reuse, no LLM-specific tuning needed
- OpenRouter provides unified API, so no direct DeepSeek account needed
