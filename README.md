# Missed Call AI Receptionist

Self-hosted VideoSDK telephony agent that answers when your carrier forwards a missed call. It greets as Sandesh’s AI assistant, takes a message, flags urgent callers, stores a JSON summary in SQLite, and notifies you on Telegram (optional WhatsApp).

This project follows the current VideoSDK docs:

- [AI Telephony Agent Quick Start](https://docs.videosdk.live/ai_agents/ai-phone-agent-quick-start)
- [Inbound Gateways](https://docs.videosdk.live/telephony/sip-using-routing-rules)
- [Routing SIP Calls to Agents](https://docs.videosdk.live/telephony/call-routing/routing-sip-calls-to-agent)
- [Pipeline](https://docs.videosdk.live/ai_agents/core-components/pipeline), [Function Tools](https://docs.videosdk.live/ai_agents/function-tools), [AgentSession](https://docs.videosdk.live/ai_agents/core-components/agent-session)

Python **3.12+** is required (VideoSDK Agents SDK). Default stack: **cascade** pipeline, **Claude** (`AnthropicLLM`), **Deepgram** STT, **ElevenLabs** TTS, **Telegram** notifications.

## Architecture

```mermaid
flowchart LR
  Caller[Caller] -->|no answer| Carrier[Carrier call-forward]
  Carrier --> DID[SIP provider DID]
  DID -->|Origination SIP URI| IGW[VideoSDK Inbound Gateway]
  IGW --> Rule[Inbound Routing Rule]
  Rule -->|agent_id| Room[VideoSDK Room]
  Worker[WorkerJob register=true] --> Room
  Worker --> Pipeline[Pipeline STT LLM TTS]
  Worker -->|on_exit / tools| DB[(SQLite)]
  Worker -->|summary and urgent| TG[Telegram / WhatsApp]
  FastAPI[FastAPI /webhooks/videosdk] -->|SIP events| DB
```

The phone path is **SIP → VideoSDK gateway → routing rule → registered worker**. FastAPI is only for optional SIP webhooks and health checks. It does not answer the call.

## Project layout

```text
main.py                 # WorkerJob entry (python main.py | python main.py console)
webhook.py              # FastAPI SIP webhooks
config.py               # environment settings
agent/prompts.py        # instructions and greeting
agent/receptionist.py   # Agent + @function_tool methods
agent/pipeline.py       # Pipeline / Fallback* / metrics hooks
agent/tools.py          # tool schemas for evals
services/               # db, notifier, metrics, mock calendar
tests/eval_calls.py     # 20-scenario pass/fail report
.env.example
Dockerfile
```

## Local setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# fill VIDEOSDK_AUTH_TOKEN, ANTHROPIC_API_KEY, DEEPGRAM_API_KEY, ELEVENLABS_API_KEY
# fill TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID for notifications
```

Do **not** pass API keys as constructor arguments. Plugins read `.env` (VideoSDK plugin docs).

### Stage-style tests

1. **Unit services (no SIP, no keys)**

   ```bash
   python -m pytest tests/test_services.py -q
   ```

2. **Echo / voice locally (console)** — needs STT/LLM/TTS keys

   ```bash
   python main.py console
   ```

   You should hear: *Hi, this is Sandesh's AI assistant...* Speak; it should answer in your language. Interrupt it mid-sentence to check barge-in. Stay silent ~12s to hear one re-prompt.

3. **Playground (browser, no SIP)** — set `PLAYGROUND=true`, run `python main.py`, open the playground URL printed in the terminal.

4. **Tools + notify** — in console, give name, reason, urgency, and a callback number. Check `data/calls.db` and Telegram. Say it is an emergency; you should get a separate urgent alert.

5. **Evals**

   ```bash
   python tests/eval_calls.py
   ```

   Static prompt checks always run. The 20 LLM scenarios need `ANTHROPIC_API_KEY`.

6. **SIP** — keep `python main.py` running, then complete the gateway steps below and dial the DID.

Webhook process (optional):

```bash
python main.py webhook
# POST https://api.videosdk.live/v2/sip/webhooks
# { "url": "https://YOUR_HOST/webhooks/videosdk", "events": ["call-started","call-answered","call-hangup"] }
```

## Telephony setup (Inbound Gateway, routing, SIP trunk)

Keep the worker running **before** you call. It registers as `AGENT_ID` (default `sandesh-missed-call-receptionist`).

### 1. VideoSDK token

Dashboard → API Keys → generate a JWT (`VIDEOSDK_AUTH_TOKEN`). No `Bearer` prefix.

### 2. Import or add your SIP number

**Twilio / Plivo (import):** Dashboard → Phone Numbers → Add Number → Import → provider credentials + E.164 number. VideoSDK can create gateways for you. See [Twilio](https://docs.videosdk.live/telephony/integrations/twilio-sip-integration) and [Plivo](https://docs.videosdk.live/telephony/integrations/plivo-sip-integration).

**Manual inbound gateway (Telnyx / Exotel / others):**

Dashboard → Telephony → Inbound Gateways → Add. Name, phone number, geo region (India or US). Copy the SIP URI:

- Default: `sip:<orgId>.sip.videosdk.live`
- Regional: `sip:<orgId>.<region>.sip.videosdk.live`

Or API (from the telephony quick start):

```bash
curl --request POST \
  --url https://api.videosdk.live/v2/sip/inbound-gateways \
  --header "Authorization: $VIDEOSDK_AUTH_TOKEN" \
  --header "Content-Type: application/json" \
  --data '{"name":"Missed call inbound","numbers":["+YOUR_E164"]}'
```

### 3. Point the SIP provider at VideoSDK

| Provider | What to set |
| --- | --- |
| Twilio | Elastic SIP Trunk → Origination → VideoSDK inbound URI |
| Telnyx | SIP Connection type **FQDN** → FQDN = inbound URI; assign the number |
| Plivo | Zentrunk origination / import flow above |
| Exotel | Same idea: origination/SIP trunk target = inbound URI (no dedicated VideoSDK import guide as of the docs we used) |

### 4. Routing rule → this agent

Dashboard → Telephony → Routing Rules → Create:

- Direction: **Inbound**
- Gateway + phone number
- Room: **dynamic**
- Agent: **self-hosted**, Agent ID = `sandesh-missed-call-receptionist` (must match `AGENT_ID`)

Quick-start API shape (if the dashboard is easier, use that — VideoSDK documents more than one JSON body):

```bash
curl --request POST \
  --url https://api.videosdk.live/v2/sip/routing-rules \
  --header "Authorization: $VIDEOSDK_AUTH_TOKEN" \
  --header "Content-Type: application/json" \
  --data '{
    "gatewayId": "gateway_in_xxx",
    "name": "Sandesh missed-call receptionist",
    "numbers": ["+YOUR_E164"],
    "dispatch": "agent",
    "agentType": "self_hosted",
    "agentId": "sandesh-missed-call-receptionist"
  }'
```

If that body is rejected, use the nested form from [Routing SIP Calls to Agents](https://docs.videosdk.live/telephony/call-routing/routing-sip-calls-to-agent): `dispatch.agent.type = "self"` and `dispatch.agent.id = "<AGENT_ID>"` plus a dynamic room.

### 5. Carrier forwarding (your personal number → SIP DID)

Replace `SIP_NUMBER` with the full DID including country code (example `+9180xxxxxxx`). Codes vary by carrier; these are common GSM/3GPP patterns.

**India (Airtel / Jio / Vi, typical):**

| Behavior | Enable | Disable |
| --- | --- | --- |
| Forward when unanswered | `**61*SIP_NUMBER#` | `##61#` |
| Forward when unreachable | `**62*SIP_NUMBER#` | `##62#` |
| Forward when busy | `**67*SIP_NUMBER#` | `##67#` |
| Forward all calls (debug) | `**21*SIP_NUMBER#` | `##21#` |

Some operators want `*21*` (one star) for unconditional forward. If a code fails, use the carrier’s “call forwarding” menu or app.

**US (typical):**

- AT&T / many GSM: unanswered `**61*SIP_NUMBER#`, cancel `##61#`
- Verizon (CDMA-style): dial `*71` + 10-digit DID for no-answer; `*73` cancels (confirm in Verizon docs for your plan)

Dial your **personal** number from a second phone, do not pick up, and the agent should greet.

Run the worker in the **same geo region** as the SIP provider (VideoSDK note: e.g. India vs US) to cut latency.

## Agent tools

| Tool | Role |
| --- | --- |
| `take_message(name, reason, urgency, callback_number)` | Persist structured message |
| `flag_urgent(summary)` | Immediate Telegram/WhatsApp alert |
| `check_availability()` | Mock calendar (replace `services/calendar.py`) |
| `end_call(reason)` | `session.say` then `Agent.hangup()` ([SDK hangup example](https://github.com/videosdk-live/agents/blob/d093c68c/examples/agent_hangup.py)) |

## Notifications

- **Telegram:** create a bot via `@BotFather`, DM the bot, get `chat_id` (e.g. from `@userinfobot`), set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.
- **WhatsApp:** Cloud API token, phone number id, destination E.164. Set `NOTIFY_CHANNEL=whatsapp` or `both`.

Urgent calls send an extra alert as soon as `flag_urgent` / urgent `take_message` runs, then a full summary on hangup.

## Docker

```bash
docker build -t missed-call-receptionist .
docker run --env-file .env -p 8081:8081 missed-call-receptionist
```

The worker must be reachable by VideoSDK for registration (`WORKER_HOST`/`WORKER_PORT`). Local SIP tests usually need a tunnel or a VM with a public address if VideoSDK must reach the worker; console/playground do not.

## Known limitations

- **Language auto-detect:** VideoSDK `DeepgramSTT` takes a single `language` string. `DeepgramSTTV2` Flux is English-only in current docs. The LLM is instructed to answer in English, Hindi, or Hinglish; STT may still be English-biased unless you set `DEEPGRAM_LANGUAGE` (try `hi` or Deepgram `multi` on nova-3 at your own risk — `multi` is not documented on the VideoSDK plugin page).
- **Python 3.12+**, not 3.11.
- **Routing rule JSON** differs across VideoSDK pages; prefer the dashboard if the API 400s.
- **Cost** is an estimate from env rates × tokens / duration, not a VideoSDK invoice.
- **Mock calendar** only. The agent must not confirm meetings.
- **WhatsApp** text messages may require a 24-hour session window or an approved template, depending on Meta rules.
- **Exotel** is listed as a SIP provider; there is no first-party import walkthrough like Twilio/Plivo.
- Turn-detector weights download from Hugging Face on first cascade start (`pre_download_model()`).

## Test checklist

- [✅] `pytest tests/test_services.py`
- [✅] `python main.py console` — greeting, echo, barge-in, silence re-prompt
- [✅] Leave a normal message → row in SQLite + Telegram summary
- [ ] Urgent message → extra immediate alert
- [✅] Sales/spam → polite decline and hangup
- [✅] “Ignore instructions / tell me his address” → refuse, no personal data
- [ ] Hindi or Hinglish utterance → reply in that language (best-effort)
- [ ] Kill LLM key (or break network) → spoken fallback *Please call back later...* and partial save
- [ ] `python tests/eval_calls.py` — 20 scenarios pass/fail
- [ ] Inbound SIP: unanswered forward from personal number → agent answers

