# Vertex AI Reasoning Proxy

A lightweight proxy server that enables OpenClaw (and other OpenAI-compatible clients) to use Google Vertex AI's Gemini 2.5 Flash with granular control over reasoning effort levels.

## Problem

OpenClaw doesn't natively support passing custom API parameters like `reasoning_effort` to Vertex AI models. This proxy solves that by:

1. **Intercepting** OpenAI-compatible API requests from OpenClaw
2. **Parsing** model IDs to determine desired reasoning level
3. **Adding** the `reasoning_effort` parameter to Vertex AI requests
4. **Forwarding** modified requests to Vertex AI
5. **Returning** responses back to OpenClaw

## Features

- ✅ **Three-tier thinking system**: Low (1K tokens) / Medium (8K tokens) / High (24K tokens)
- ✅ **OpenAI-compatible API**: Works with OpenClaw and other clients
- ✅ **Automatic token refresh**: Uses `gcloud` for fresh tokens
- ✅ **Zero configuration needed in OpenClaw**: Just change the base URL
- ✅ **Lightweight**: FastAPI-based, minimal dependencies
- ✅ **Easy deployment**: Run as systemd/launchd service

## Architecture

```
┌──────────┐         ┌───────────────┐         ┌─────────────┐
│ OpenClaw │────────>│  Proxy Server │────────>│  Vertex AI  │
└──────────┘         │  localhost:8000│         │   Gemini    │
                     └───────────────┘         └─────────────┘
                            │
                     Model ID Parsing:
                     ├─ *-low    → reasoning_effort: "low"
                     ├─ *-medium → reasoning_effort: "medium"
                     └─ *-high   → reasoning_effort: "high"
```

## Prerequisites

- Python 3.9+
- Google Cloud SDK (`gcloud`)
- Vertex AI API enabled
- Application Default Credentials configured

```bash
# Install gcloud
# See: https://cloud.google.com/sdk/docs/install

# Authenticate
gcloud auth application-default login

# Set project
gcloud config set project YOUR_PROJECT_ID
```

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/vertexai-proxy.git
cd vertexai-proxy
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env with your Vertex AI project details
```

### 4. Run the proxy

```bash
python proxy.py
```

The server will start on `http://127.0.0.1:8000`

## Usage

### Test the proxy

```bash
# Health check
curl http://localhost:8000/health

# Test completion (low reasoning)
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "google/gemini-2.5-flash-low",
    "messages": [{"role": "user", "content": "What is 2+2?"}]
  }'
```

### Configure OpenClaw

Edit `~/.openclaw/openclaw.json`:

```json
{
  "models": {
    "mode": "merge",
    "providers": {
      "vertexai-proxy": {
        "baseUrl": "http://127.0.0.1:8000/v1",
        "apiKey": "dummy-key-not-used",
        "api": "openai-completions",
        "models": [
          {
            "id": "google/gemini-2.5-flash-low",
            "name": "Gemini 2.5 Flash (Low)",
            "reasoning": true,
            "contextWindow": 1048576,
            "maxTokens": 8192
          },
          {
            "id": "google/gemini-2.5-flash-medium",
            "name": "Gemini 2.5 Flash (Medium)",
            "reasoning": true,
            "contextWindow": 1048576,
            "maxTokens": 8192
          },
          {
            "id": "google/gemini-2.5-flash-high",
            "name": "Gemini 2.5 Flash (High)",
            "reasoning": true,
            "contextWindow": 1048576,
            "maxTokens": 8192
          }
        ]
      }
    }
  },
  "agents": {
    "defaults": {
      "model": {
        "primary": "vertexai-proxy/google/gemini-2.5-flash-medium"
      },
      "heartbeat": {
        "model": "vertexai-proxy/google/gemini-2.5-flash-low"
      },
      "subagents": {
        "model": "vertexai-proxy/google/gemini-2.5-flash-high",
        "maxConcurrent": 8
      }
    }
  }
}
```

## Running as a Service

### macOS (launchd)

Create `~/Library/LaunchAgents/com.vertexai.proxy.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.vertexai.proxy</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/YOUR_USERNAME/vertexai-proxy/proxy.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/vertexai-proxy.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/vertexai-proxy.err.log</string>
</dict>
</plist>
```

Load the service:

```bash
launchctl load ~/Library/LaunchAgents/com.vertexai.proxy.plist
```

### Linux (systemd)

Create `/etc/systemd/system/vertexai-proxy.service`:

```ini
[Unit]
Description=Vertex AI Reasoning Proxy
After=network.target

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/home/YOUR_USERNAME/vertexai-proxy
ExecStart=/usr/bin/python3 /home/YOUR_USERNAME/vertexai-proxy/proxy.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable vertexai-proxy
sudo systemctl start vertexai-proxy
```

## Model ID Format

The proxy parses model IDs with the following pattern:

- `google/gemini-2.5-flash-low` → `reasoning_effort: "low"` (1K tokens)
- `google/gemini-2.5-flash-medium` → `reasoning_effort: "medium"` (8K tokens)
- `google/gemini-2.5-flash-high` → `reasoning_effort: "high"` (24K tokens)
- `google/gemini-2.5-flash` → `reasoning_effort: "medium"` (default)

## Cost Optimization

By routing different agent types to appropriate thinking levels:

| Agent Type | Reasoning Level | Reasoning Tokens | Use Case |
|------------|----------------|------------------|----------|
| Heartbeat | Low | ~1K | Quick checks, simple queries |
| Main Agent | Medium | ~8K | Standard conversations |
| Subagents | High | ~24K | Complex tasks, deep reasoning |

**Estimated savings**: 40-60% on reasoning token costs vs. always using high reasoning.

## Troubleshooting

### "Failed to get access token"

Ensure `gcloud` is authenticated:

```bash
gcloud auth application-default login
```

### Port already in use

Change the port in `.env` or `proxy.py`:

```python
PROXY_PORT=8001
```

### OpenClaw can't connect

Verify the proxy is running:

```bash
curl http://localhost:8000/health
```

## Development

### Run in development mode

```bash
uvicorn proxy:app --reload --host 127.0.0.1 --port 8000
```

### Add logging

```bash
python proxy.py 2>&1 | tee proxy.log
```

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License - see LICENSE file for details

## Acknowledgments

- Built for [OpenClaw](https://openclaw.ai/)
- Uses Google Cloud Vertex AI
- Inspired by the need for granular reasoning control

## Support

- **Issues**: https://github.com/YOUR_USERNAME/vertexai-proxy/issues
- **Discussions**: https://github.com/YOUR_USERNAME/vertexai-proxy/discussions

---

**Built with ❤️ for the OpenClaw community**
