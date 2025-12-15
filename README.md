# Prediction Bot

Multi-instance behavioral coaching Telegram bot using prediction error architecture.

## Architecture Overview

```
prediction-bot/
├── bot.py                    # Main Telegram handler
├── config.py                 # Configuration and API keys
├── requirements.txt          # Dependencies
│
├── core/                     # Core modules
│   ├── security.py           # Input/output security filtering
│   ├── llm.py                # LLM client with prompt caching
│   └── extraction.py         # Data extraction from conversations
│
├── memory/                   # Memory management
│   ├── state.py              # User state (phase, progression, patterns)
│   ├── facts.py              # Long-term facts storage
│   ├── history.py            # Conversation history
│   ├── episodic.py           # Significant moments
│   └── scheduled.py          # Re-engagement scheduling
│
├── engine/                   # Response generation
│   └── response.py           # Main response engine
│
├── instances/                # Bot instance definitions
│   ├── base/                 # Shared framework
│   │   ├── core_framework.md # Prediction error framework
│   │   └── security_rules.md # Security rules
│   │
│   ├── elite_coach/          # First dollar coaching
│   │   ├── definition.json   # Steps, endpoint, anti-patterns
│   │   └── persona.md        # Voice and personality
│   │
│   ├── move_prompt/          # Movement habit building
│   │   ├── definition.json
│   │   └── persona.md
│   │
│   └── morning_protocol/     # Morning phone control
│       ├── definition.json
│       └── persona.md
│
└── data/                     # User data (auto-created)
    └── users/
        └── {user_id}/
            ├── state.json    # Current state
            ├── facts.json    # Extracted facts
            ├── history.json  # Full conversation
            ├── history.txt   # Human-readable log
            ├── episodic.json # Significant moments
            ├── activity.json # Activity patterns
            └── scheduled.json # Pending messages
```

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API Keys

Edit `config.py` or set environment variables:

```bash
export TELEGRAM_BOT_TOKEN="your-telegram-bot-token"
export ANTHROPIC_API_KEY="your-anthropic-api-key"
export OPENAI_API_KEY="your-openai-api-key"  # For voice transcription
export ELEVENLABS_API_KEY="your-elevenlabs-key"  # Optional, for TTS
```

### 3. Create Telegram Bot

1. Message @BotFather on Telegram
2. Send `/newbot` and follow prompts
3. Copy the token to `TELEGRAM_BOT_TOKEN`

### 4. Run

```bash
python bot.py
```

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Begin or restart |
| `/clear` | Delete all user data |
| `/stats` | View progress |
| `/voice` | Toggle voice responses |
| `/save [text]` | Pin something to remember |
| `/recall` | View saved items |
| `/forget [#]` | Remove saved item |
| `/help` | Show help |

## How It Works

### Phases

1. **First Contact** → Privacy agreement
2. **Onboarding** → Natural conversation to collect 4 data points
3. **Coaching** → Incremental revelation with step-by-step gating
4. **Post-Success** → Choose: lock in, level up, or done
5. **Maintenance** → Reduced frequency check-ins

### Memory Tiers

| Tier | Always Loaded | Purpose |
|------|---------------|---------|
| STATE | ✓ | Current phase, step, pattern flags |
| RECENT | ✓ | Last 5 messages |
| FACTS | ✓ | Extracted user facts, pinned items |
| EPISODIC | Conditional | Breakthroughs, completions |
| HISTORY | Never | Full log, user export only |

### Security Layers

1. **Input Sanitization** - Injection detection, obfuscation normalization
2. **Output Filtering** - Prompt leakage prevention
3. **Rate Limiting** - Per-minute and per-hour limits
4. **Conversation Monitoring** - Multi-turn manipulation detection

## Creating a New Instance

1. Copy an existing instance folder:
```bash
cp -r instances/elite_coach instances/my_instance
```

2. Edit `definition.json`:
   - `instance_id` - Unique identifier
   - `endpoint` - What success looks like
   - `constraint` - The true blocker
   - `steps` - Atomic actions (under 10 min each)
   - `anti_patterns` - How users avoid action
   - `tone` - Voice and personality rules

3. Edit `persona.md`:
   - Who the coach is
   - How they speak
   - What they never do

4. Update routing in `core/extraction.py`:
   - Add keywords to `DOMAIN_KEYWORDS`

## Cost Optimization

- **Prompt Caching**: System prompt + frameworks cached for 90% savings
- **Tiered Memory**: Only load what's needed
- **Fast Extraction Model**: Uses Sonnet for quick classification tasks
- **Session-Based Extraction**: Extract facts on session end, not every message

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | Telegram bot token |
| `ANTHROPIC_API_KEY` | Yes | Claude API key |
| `OPENAI_API_KEY` | For voice | Whisper transcription |
| `ELEVENLABS_API_KEY` | Optional | Text-to-speech |

## File Formats

### state.json
```json
{
  "phase": "coaching",
  "instance_type": "elite_coach",
  "progression": {
    "current_step": "Create BMC account",
    "current_step_id": 1,
    "completed_steps": []
  },
  "pattern_flags": {
    "intellectualizing": 0.2,
    "chat_without_action": 0
  }
}
```

### definition.json
```json
{
  "instance_id": "my_instance",
  "endpoint": {
    "description": "What success looks like",
    "success_keywords": ["done", "achieved"]
  },
  "steps": [
    {
      "id": 1,
      "action": "First thing to do",
      "time_limit": "5 minutes",
      "completion_signals": ["done", "did it"]
    }
  ]
}
```

## Deployment

### Railway (Recommended)

1. **Push to GitHub**
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin <your-repo-url>
git push -u origin main
```

2. **Connect Railway**
   - Go to [railway.app](https://railway.app)
   - New Project → Deploy from GitHub repo
   - Select your repository

3. **Set Environment Variables**
   - In Railway dashboard → Variables
   - Add each variable from `.env.example`:
     - `TELEGRAM_BOT_TOKEN`
     - `ANTHROPIC_API_KEY`
     - `OPENAI_API_KEY`
     - `ELEVENLABS_API_KEY` (optional)

4. **Deploy**
   - Railway auto-deploys on push
   - Check logs for "Starting Prediction Bot..."

### Railway with Persistent Storage

By default, Railway's filesystem resets on redeploy. For persistent user data:

**Option A: Railway Volume (Simple)**
- Add a Volume in Railway dashboard
- Mount at `/app/data`
- Update `config.py`: `DATA_DIR = Path("/app/data/users")`

**Option B: External Database (Scalable)**
- See "Scaling to 1000+ Users" section below

### VPS (DigitalOcean, Linode, etc.)

```bash
# Install
git clone <repo>
cd prediction-bot
pip install -r requirements.txt

# Run with systemd or screen
screen -S bot
python bot.py
```

## License

MIT

---

## Scaling to 1000+ Users

### Current Architecture Limits

The current file-based architecture works well up to ~100-200 concurrent users:

| Component | Current | Bottleneck At Scale |
|-----------|---------|---------------------|
| Storage | JSON files | Slow reads/writes with 1000+ user directories |
| Scheduled Messages | Directory scan every 60s | O(n) scan of all users |
| LLM Calls | Sequential | API rate limits, response latency |
| Bot Process | Single | Memory limits, no failover |

### What 1000 Users Actually Means

Not all users are active simultaneously:
- 1000 total users ≠ 1000 concurrent users
- Typical: 5-10% daily active = 50-100 concurrent
- Peak: Maybe 20-30 simultaneous conversations

**At 1000 total users, the current architecture will likely work**, but you'll notice:
- Slower scheduled message delivery
- Occasional latency spikes
- Higher memory usage

### When to Scale

Scale when you see:
- Response times > 3 seconds consistently
- Scheduled messages delayed by minutes
- Memory usage approaching Railway limits
- User complaints about slowness

### Scaled Architecture

```
                    ┌─────────────────┐
                    │   Telegram API  │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  Load Balancer  │
                    │   (optional)    │
                    └────────┬────────┘
                             │
           ┌─────────────────┼─────────────────┐
           │                 │                 │
    ┌──────▼──────┐   ┌──────▼──────┐   ┌──────▼──────┐
    │  Worker 1   │   │  Worker 2   │   │  Worker 3   │
    │  (bot.py)   │   │  (bot.py)   │   │  (bot.py)   │
    └──────┬──────┘   └──────┬──────┘   └──────┬──────┘
           │                 │                 │
           └─────────────────┼─────────────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
       ┌──────▼──────┐ ┌─────▼─────┐ ┌─────▼─────┐
       │  PostgreSQL │ │   Redis   │ │ Anthropic │
       │ (user data) │ │  (cache)  │ │    API    │
       └─────────────┘ └───────────┘ └───────────┘
```

### Migration Path

**Phase 1: Database (100-500 users)**
Replace JSON files with PostgreSQL:

```python
# Instead of memory/state.py reading JSON files
# Use SQLAlchemy or asyncpg

from sqlalchemy import create_engine
engine = create_engine(os.getenv("DATABASE_URL"))
```

Tables needed:
- `users` (id, created_at, instance_type, phase)
- `state` (user_id, current_step, pattern_flags, etc.)
- `facts` (user_id, key, value)
- `history` (user_id, role, content, timestamp)
- `scheduled` (user_id, send_at, type, status)

**Phase 2: Redis Cache (500-2000 users)**
Add Redis for:
- Session caching (recent messages)
- Rate limiting
- Scheduled message queue

```python
import redis
r = redis.from_url(os.getenv("REDIS_URL"))

# Cache recent messages
r.setex(f"recent:{user_id}", 3600, json.dumps(messages))
```

**Phase 3: Worker Processes (2000+ users)**
Run multiple bot instances:

```yaml
# railway.json or docker-compose.yml
services:
  bot-worker-1:
    command: python bot.py
  bot-worker-2:
    command: python bot.py
  scheduler:
    command: python scheduler.py  # Separate scheduled message handler
```

Use Telegram webhooks instead of polling:
```python
# Webhooks scale better than polling
application.run_webhook(
    listen="0.0.0.0",
    port=int(os.getenv("PORT", 8443)),
    webhook_url=f"https://{os.getenv('RAILWAY_STATIC_URL')}/webhook"
)
```

### Cost at Scale

| Users | Est. Monthly LLM Cost | Infrastructure |
|-------|----------------------|----------------|
| 100 | $20-50 | Railway Hobby ($5) |
| 500 | $100-250 | Railway Pro ($20) + PostgreSQL |
| 1000 | $200-500 | Railway Pro + PostgreSQL + Redis |
| 5000 | $1000-2500 | Dedicated infrastructure |

*Assumes ~20 messages/user/month, prompt caching active*

### Quick Wins Before Full Migration

If you're at 500 users and seeing slowness:

1. **Index scheduled messages by time**
   - Instead of scanning all users, maintain a sorted queue

2. **Lazy load user data**
   - Only load full history when needed
   - Keep state/facts small

3. **Batch LLM calls**
   - Use prompt caching aggressively
   - Consider Haiku for extraction tasks

4. **Add connection pooling**
   - Reuse HTTP connections to Anthropic API

