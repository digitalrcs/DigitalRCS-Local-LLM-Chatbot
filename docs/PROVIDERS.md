# Choose where Franky gets his answers

**LM Studio is the default.** Franky never automatically switches providers. Liam's voice and English speech recognition run on the bridge PC for every option below.

For a new installation, follow the [Windows setup app guide](WINDOWS-INSTALLER.md). Choose where answers come from on its **Answers** step. You can change that choice later without reinstalling Franky or updating the robot.

| Choice | Where text goes | What you need | Cost/availability |
| --- | --- | --- | --- |
| LM Studio | Your own PC or home-network server | LM Studio and a loaded chat model | No online inference bill; requires suitable hardware |
| OpenAI API | OpenAI | An API account, key, and supported text model | Metered API usage; check your account's credits and limits |
| OpenRouter free models | OpenRouter and its selected model provider | OpenRouter account/key | Only `openrouter/free` or `:free` model IDs accepted; availability and rate limits vary |
| Gemini | Google | Gemini API key and eligible model/account | Some models/accounts have a free tier; paid usage is possible depending on your account and selection |

Online mode sends the transcribed conversation and recent context outside your home network. It does not upload microphone recordings through this chat integration. Provider data policies still apply. Local mode remains available without any cloud key.

## Change provider in the Windows setup app

1. Open **Franky Setup**. If the bridge is running, choose **Stop bridge** on **Try it**. A copy started from a command window must be stopped in that window with **Ctrl+C**.
2. Open **Answers** and choose the **Answer provider**.
3. For LM Studio on this PC, use **Install LM Studio** if needed, download and load a chat model in LM Studio, then choose **Start LM Studio**. For an existing server on another PC, select **LM Studio is on another PC or needs a token** and enter its address instead. The same checkbox reveals the token field when your server requires one.
4. For an online provider, read the note, select the consent checkbox, and enter your key in the masked **API key** field. Leave it blank to keep an existing saved key.
5. Choose **Find models**, select a text chat model, then choose **Save answer settings**.
6. Return to **Try it**, choose **Start bridge**, then **Check readiness**. Ask Franky a short question to test the change.

Saved keys are protected for your Windows account. No cloud key is included, and local LM Studio does not require one. To return to local answers, choose **LM Studio — local PC or home network** and save its model again.

## Manual source installation: change provider

These command-window steps are for the source ZIP/manual installation.

1. Stop the bridge with **Ctrl+C** in its running window.
2. Double-click **CHANGE-PROVIDER.cmd**.
3. Choose a provider. Pressing Enter selects **LM Studio**.
4. For an online provider, read the privacy/cost message and confirm your choice.
5. Enter your API key into the **local setup window** when prompted. The characters are hidden. Never paste keys into a chat, GitHub issue, or robot setup page.
6. If you choose to save the key, Windows protects it for your current Windows account in `bridge/.secrets`. This folder is excluded from Git and release packages. Environment variables, if configured, take precedence.
7. Choose a **text chat model** from the returned model list. Some providers also list image, audio, embedding, or other models; a listed ID alone does not mean it supports this chat interface.
8. Start **START-FRANKY.cmd** again. Use **CHECK-SETUP.cmd** to check the selected provider and model listing.

No cloud key is bundled with this project. A key is not required to finish installing the local LM Studio setup. To return to local processing, rerun CHANGE-PROVIDER and choose option 1; the saved local address and model remain available.

## Free online choices

OpenRouter's [`openrouter/free` router](https://openrouter.ai/docs/guides/routing/routers/free-router) selects an available free model. That can mean different models answer different requests. Alternatively, select a specific model whose ID ends in `:free`. This application rejects other OpenRouter model IDs and has no paid fallback. Free requests can still fail because of capacity, quotas, or account restrictions; see [OpenRouter limits](https://openrouter.ai/docs/api_reference/limits).

Gemini's [pricing page](https://ai.google.dev/gemini-api/docs/pricing) distinguishes free and paid tiers. Check the selected model and account before use. This application cannot independently guarantee that a Gemini request is free. Google's free-tier data terms may differ from paid-tier terms.

Local LM Studio is the option for keeping conversation text on your own machines and avoiding online service quotas.

## OpenAI details

The OpenAI option uses the [Responses API](https://developers.openai.com/api/docs/guides/text), with `store: false`, and reads assistant text separately from reasoning items. This option uses an OpenAI API key; it does not sign into the ChatGPT website. Review the API account's billing and credit status before use.

OpenAI requests go only to the fixed official HTTPS endpoint. OpenRouter and Gemini likewise use fixed HTTPS endpoints. Redirects are not followed when sending credentials. There is no automatic retry on a different provider or paid model.

Cloud adapters are tested using simulated provider responses. Live OpenAI, Gemini, and authenticated OpenRouter generation require your own keys and are not claimed as verified merely because unit tests pass.

## Keys, moving PCs, and troubleshooting

- If a key was exposed, revoke it at the provider and enter a replacement locally.
- Windows-protected keys cannot simply be copied to another PC/account. Enter them again after moving the project.
- You can instead configure `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, `GEMINI_API_KEY`, or `LM_STUDIO_TOKEN` in the bridge process environment. Do not commit them.
- A 401/403 error means the key, account, or model access needs attention. A 429 means wait for the provider's quota/capacity to recover. No paid fallback is attempted.
- In a bridge started with the manual scripts, `CHAT_PROVIDER` and `CHAT_MODEL` environment variables override saved selection. The Windows setup app starts its bridge using the provider, model and addresses saved in the app. API-key environment variables can still take precedence; remove a conflicting key override before saving a replacement.
- `max_output_tokens` in `bridge/config.json` defaults to 1200 and accepts 128–4096. Explicit saved values are preserved. The budget includes reasoning: Gemma can exhaust 256 tokens without producing an answer. Keep sufficient room for reasoning even though Franky requests short spoken replies. An output-limit failure is reported; streamed sentences already played cannot be recalled, but the partial answer is not saved as a completed turn.
- `disable_thinking` (default `true`) adds `/no_think` for Qwen3-family models whose templates support it. It does not disable Gemma's reasoning. Gemma 4 uses [its own thinking controls](https://ai.google.dev/gemma/docs/capabilities/thinking); the active LM Studio model/template determines its behavior. Reducing reasoning can change answer quality as well as speed.

The bridge is still a trusted-home-network service without a login. Anyone who can reach it may consume the selected provider's quota or credits. Do not expose port 8766 to the Internet.
