# AI Receptionist

A phone agent that answers your missed calls. It greets the caller as Sandesh's AI assistant, takes a message, flags urgent calls, saves a summary to SQLite, and sends it to you on Telegram (WhatsApp optional).

## How it works

```
Caller → your carrier (no answer) → forwards to SIP number
       → VideoSDK gateway → routing rule → your running worker (STT → LLM → TTS)
       → saves to SQLite + notifies you on Telegram
```

The worker (`python main.py`) answers the call. FastAPI is only for optional webhooks.

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env`:

- `VIDEOSDK_AUTH_TOKEN`
- `ANTHROPIC_API_KEY`
- `DEEPGRAM_API_KEY`
- `ELEVENLABS_API_KEY`
- `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`

Python 3.12+ is required. Don't pass API keys in code; the plugins read `.env`.

## Try it locally (no phone needed)

```bash
python -m pytest tests/test_services.py -q   # unit tests
python main.py console                       # talk to it in your terminal
python tests/eval_calls.py                   # 20 test scenarios
```

In console mode, check that it greets you, replies in your language, handles interruptions, and saves a message to `data/calls.db` and Telegram.

## Connect a real phone number

Keep `python main.py` running first.

1. **Get a SIP number** (Twilio, Plivo, Telnyx, or Exotel).
2. **Create an inbound gateway** in the VideoSDK dashboard: Telephony → Inbound Gateways → Add. Copy the SIP URI (`sip:<orgId>.sip.videosdk.live`).
3. **Point your SIP provider at that URI** (set it as the origination target).
4. **Create a routing rule**: Telephony → Routing Rules → Create.
   - Direction: Inbound
   - Room: dynamic
   - Agent: self-hosted, ID = `sandesh-missed-call-receptionist` (must match `AGENT_ID`)
5. **Forward missed calls** from your personal number to the SIP number:

| Action | Dial |
| --- | --- |
| Forward when unanswered | `**61*SIP_NUMBER#` |
| Forward when unreachable | `**62*SIP_NUMBER#` |
| Forward when busy | `**67*SIP_NUMBER#` |
| Turn off unanswered forwarding | `##61#` |

Use the full number with country code. If a code fails, use your carrier's call-forwarding settings.

Test it: call your number from another phone and don't answer.

## Agent tools

| Tool | What it does |
| --- | --- |
| `take_message` | Saves name, reason, urgency, callback number |
| `flag_urgent` | Sends an instant alert |
| `check_availability` | Mock calendar (never confirms meetings) |
| `end_call` | Says goodbye and hangs up |

## Notifications

- **Telegram:** create a bot with `@BotFather`, message it, and get your chat ID from `@userinfobot`.
- **WhatsApp (optional):** set `NOTIFY_CHANNEL=whatsapp` or `both` and add your Cloud API details.

Urgent calls trigger an immediate alert, then a full summary when the call ends.

## Docker

```bash
docker build -t missed-call-receptionist .
docker run --env-file .env -p 8081:8081 missed-call-receptionist
```

## Known limitations

- Speech recognition is English-biased. Set `DEEPGRAM_LANGUAGE` (e.g. `hi`) for Hindi.
- If the routing-rule API returns an error, use the dashboard instead.
- Cost figures are estimates, not VideoSDK invoices.
- WhatsApp may need an approved template outside the 24-hour window.

## Still to test

- [ ] Urgent alert
- [ ] Hindi/Hinglish reply
- [ ] LLM failure fallback
- [ ] `python tests/eval_calls.py`
- [ ] Real inbound SIP call
