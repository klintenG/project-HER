# Gemini authentication failure during input resolution

For job `d17de95bacc2`, generation stopped in `input_fetch_and_extract` before
narration, image generation or rendering. The effective Gemini credential matched
the project's `.env`; no whitespace or conflicting loaded value was found.
The credential value was not printed or changed.

Read-only checks outside ProjectHER reproduced Google's rejection:

| Request | Authentication | Result |
|---|---|---|
| Native model list | `x-goog-api-key` | 401, `ACCESS_TOKEN_TYPE_UNSUPPORTED` |
| Native model list | Bearer | 401, `API_KEY_SERVICE_BLOCKED` for `generativelanguage.googleapis.com` |
| OpenAI-compatible model list | Bearer | 401, `ACCESS_TOKEN_TYPE_UNSUPPORTED` |

These results establish that the configured credential is currently rejected for
these endpoints. They do not establish whether the cause is a malformed/revoked
key, its API restrictions, its service-account binding/permissions, or a Google
service issue. An `AQ.` prefix alone is not an invalid-key test: Google supports
both standard and authorization keys.

## Recovery

1. Open [Google AI Studio API keys](https://aistudio.google.com/apikey). Select the
   intended project and inspect the key. Check that the project's Gemini API
   (`generativelanguage.googleapis.com`) is enabled and the key's API restrictions
   and associated permissions allow access. If the key remains rejected, create
   a replacement Gemini key for that project.
2. Update `GEMINI_API_KEY` in the project's `.env` locally. Do not paste the key
   into chat or logs. In this installation `GOOGLE_TTS_API_KEY` held the same
   rejected value: if using Google narration, update that setting too or remove
   the override so narration inherits `GEMINI_API_KEY`.
3. Restart ProjectHER so its imported configuration and clients use the new value.
4. Retry generation. Live video generation remains unverified until Google accepts
   the credential.

See Google's current [key setup and restrictions guide](https://ai.google.dev/gemini-api/docs/api-key)
and [compatibility authentication examples](https://ai.google.dev/gemini-api/docs/openai).
The code follows the documented compatibility endpoint and Bearer format.

`NewsLLM` now reports an actionable provider-specific configuration error on HTTP
401 without copying Google's response body or credentials to the UI. Other errors
retain their existing handling. Providers, model settings, image prompts and
motion behavior were not changed for this authentication issue.

Validation: 60 tests passed across `tests.test_news_auth`, `tests.test_news` and
`tests.test_event_storyboard`. New checks cover sanitized Gemini/Google errors,
Groq-specific instructions, preservation of rate-limit errors and successful JSON
responses. The external probes listed above did not generate model content.
