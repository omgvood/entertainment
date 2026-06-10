# Update .env.example for DeepSeek Support

To manually update your `parser/.env.example` file, add the following line after the `GROQ_MODEL` line:

```bash
# DeepSeek via OpenRouter (обязателен если используется DeepSeek или нужна поддержка --provider deepseek)
# API ключ из https://openrouter.ai/keys
DEEPSEEK_API_KEY=your-openrouter-api-key
DEEPSEEK_MODEL=deepseek/deepseek-v4-flash
```

Or copy the complete new version from `parser/DEEPSEEK_SETUP.md` section "Update Dependencies".

## Quick Start

1. Get OpenRouter API Key: https://openrouter.ai/keys
2. Add to your `.env` file:
   ```bash
   DEEPSEEK_API_KEY=your-openrouter-api-key
   ```
3. Test with:
   ```bash
   python -m parser.cli run --city perm --provider deepseek --dry-run
   ```
