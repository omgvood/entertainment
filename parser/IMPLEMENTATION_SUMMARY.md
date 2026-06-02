# DeepSeek V4 Integration - Implementation Summary

## Changes Made

### 1. **New File: `src/parser/extraction/deepseek_extractor.py`**
- Implements `LLMExtractor` interface
- Uses OpenAI SDK with OpenRouter API (`https://openrouter.ai/api/v1`)
- Supports both single (`extract()`) and batch (`extract_many()`) event extraction
- Model: `deepseek/deepseek-v4-flash` (customizable via env)
- Reuses system prompts and validation logic from Groq implementation
- ~270 LOC

### 2. **Updated: `src/parser/config.py`**
- Added `"deepseek"` to `LlmProvider` Literal type
- Added `"deepseek": "deepseek/deepseek-v4-flash"` to `DEFAULT_MODELS`
- Added `deepseek_api_key: Optional[str]` field to `Settings`
- Added `deepseek_model: Optional[str]` field to `Settings`
- Updated `model_for()` method to handle deepseek
- Updated `from_env()` to load `DEEPSEEK_API_KEY` and `DEEPSEEK_MODEL` from environment
- Updated validation to accept "deepseek" as valid provider

### 3. **Updated: `src/parser/cli.py`**
- Added import: `from .extraction import DeepSeekExtractor`
- Updated `_make_extractor()` function to handle `provider == "deepseek"`
- Updated `--provider` argument choices to include `"deepseek"`

### 4. **Updated: `src/parser/extraction/__init__.py`**
- Added import: `from .deepseek_extractor import DeepSeekExtractor`
- Added `DeepSeekExtractor` to `__all__` exports

### 5. **Updated: `pyproject.toml`**
- Added `"openai>=1.0,<2.0"` to dependencies
- OpenAI SDK is compatible with OpenRouter API

### 6. **Updated: `config/seeds.yaml`**
- Added commented-out test source for DeepSeek
- Users can uncomment to test DeepSeek locally on QuizPlease Perm

### 7. **New File: `DEEPSEEK_SETUP.md`**
- Complete setup guide
- API key retrieval instructions
- Usage examples (CLI flag, env variable)
- Local development instructions
- Troubleshooting guide
- Performance notes

### 8. **New File: `tests/test_extractors.py`**
- Unit tests for DeepSeekExtractor
- Mock tests for `extract()` and `extract_many()` methods
- Error handling tests (NOT_AN_EVENT, invalid JSON)
- No real API calls (all mocked)

## Verification

✓ All Python files are syntactically correct
✓ CLI correctly recognizes `--provider deepseek`
✓ DeepSeekExtractor initializes successfully
✓ Config properly loads DEEPSEEK_API_KEY from environment
✓ Tests compile without errors

## Usage

### Quick Start

1. Get API key from OpenRouter: https://openrouter.ai/keys
2. Add to `.env`:
   ```bash
   DEEPSEEK_API_KEY=your-openrouter-api-key
   ```
3. Run:
   ```bash
   python -m parser.cli run --city perm --provider deepseek --dry-run
   ```

### Full Setup

See `DEEPSEEK_SETUP.md` for comprehensive guide

## Design Decisions

1. **OpenRouter API**: Unified API for multiple models, no direct DeepSeek account needed
2. **System Prompts**: Reused from Groq implementation (no LLM-specific tuning needed)
3. **API Pattern**: OpenAI SDK compatible, follows Groq pattern for consistency
4. **Optional**: DeepSeek is opt-in; Gemini remains default, Groq as fallback
5. **No Breaking Changes**: Existing Gemini/Groq configs unaffected

## Files Modified

- `src/parser/extraction/deepseek_extractor.py` (NEW)
- `src/parser/config.py` (4 changes: 1 type, 1 dict, 2 dataclass fields, 2 methods)
- `src/parser/cli.py` (3 changes: 1 import, 1 function, 1 argument)
- `src/parser/extraction/__init__.py` (2 changes: 1 import, 1 export)
- `pyproject.toml` (1 change: added openai dependency)
- `config/seeds.yaml` (1 change: added commented test source)
- `.env.example` (NEEDS MANUAL UPDATE - see DEEPSEEK_ENV_UPDATE.md)

## Testing

Unit tests created but require pytest-asyncio plugin for full execution. Syntax checks passed.

## Next Steps for User

1. Update `.env.example` manually (see DEEPSEEK_ENV_UPDATE.md)
2. Get OpenRouter API key
3. Test with dry-run: `python -m parser.cli run --city perm --provider deepseek --dry-run`
4. Run full pipeline when ready
