# 🌐 SOA1 Remote Access Setup

This guide explains how to set up remote access to your SOA1 system using Tailscale and the web interface.

## 🎯 Overview

Your SOA1 system will be accessible remotely via:
- **Web Interface**: Chat with SOA1 through a browser
- **API Access**: Programmatic access to SOA1 functions
- **TTS Support**: Hear SOA1's responses via text-to-speech

## 🚀 Setup Instructions

### 1. Install Dependencies

```bash
# On the remote server (your friend's machine)
sudo apt update
sudo apt install curl python3-pip git
```

### 2. Install Tailscale

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo systemctl enable --now tailscaled
```

### 3. Authenticate Tailscale

```bash
sudo tailscale up
```

Follow the authentication link to connect to your Tailscale network.

### 4. Get Your Tailscale IP

```bash
tailscale ip -4
```

This will show your Tailscale IP address (e.g., `100.x.y.z`).

### 5. Install Python Dependencies

```bash
pip3 install torch torchaudio transformers soundfile fastapi uvicorn jinja2 python-multipart
```

### 6. Start Services

```bash
# Start SOA1 API (if not already running)
cd /home/ryzen/projects/home-ai/soa1
nohup python3 api.py > /tmp/soa1_api.log 2>&1 &

# Start Web Interface
nohup python3 web_interface.py > /tmp/soa1_web.log 2>&1 &
```

### 7. Access from Your Local Machine

On your local computer:

```bash
# Install Tailscale
tailscale up

# Then access the web interface
firefox http://100.x.y.z:8002  # Replace with your Tailscale IP
```

## 📋 Service Ports

| Service | Port | Description |
|---------|------|-------------|
| Web Interface | 8002 | Browser-based chat UI |
| SOA1 API | 8001 | REST API endpoints |
| MemLayer | 8000 | Memory service |
| Ollama | 11434 | LLM inference |

## 🔧 Configuration

Edit `config.yaml` to customize:

```yaml
tts:
  enabled: true          # Enable TTS
  model: "microsoft/VibeVoice-Realtime-0.5B"  # TTS model
  speaker_id: 0         # Speaker voice
  output_dir: "/tmp/soa1_tts"  # Audio output directory
```

## 🎧 Using TTS

### Via Web Interface
1. Go to the chat page
2. Ask a question
3. If TTS is enabled, you'll see an audio player with the response

### Via API

```bash
# Get text response with TTS
curl -X POST http://localhost:8001/ask-with-tts \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the weather today?"}'

# Returns:
{
  "audio_path": "/tmp/soa1_tts/response_20231213_143022.wav",
  "duration": 2.45,
  "answer": "I don't have real-time weather data..."
}

# Play the audio
aplay /tmp/soa1_tts/response_20231213_143022.wav
```

## 🛡️ Security Notes

1. **Tailscale Security**: All traffic is encrypted end-to-end
2. **Local Only**: No ports are exposed to the public internet
3. **Authentication**: Tailscale handles authentication
4. **Data Privacy**: All processing happens on the remote server

## 🔄 Systemd Services (Optional)

For automatic startup:

```bash
# Create service file
sudo nano /etc/systemd/system/soa1-web.service

# Add this content:
[Unit]
Description=SOA1 Web Interface
After=network.target

[Service]
User=ryzen
WorkingDirectory=/home/ryzen/projects/home-ai/soa1
ExecStart=/usr/bin/python3 /home/ryzen/projects/home-ai/soa1/web_interface.py
Restart=always
RestartSec=5
Environment=PYTHONPATH=/home/ryzen/projects/home-ai

[Install]
WantedBy=multi-user.target

# Enable and start
sudo systemctl enable soa1-web
sudo systemctl start soa1-web
```

## 🐛 Troubleshooting

### Tailscale Issues

```bash
# Check Tailscale status
tailscale status

# Check connection
tailscale ping 100.x.y.z
```

### Service Issues

```bash
# Check web interface logs
tail -f /tmp/soa1_web.log

# Check API logs
tail -f /tmp/soa1_api.log
```

### TTS Issues

```bash
# Test TTS directly
python3 -c "
from tts_service import VibeVoiceTTS
tts = VibeVoiceTTS()
result = tts.text_to_speech('Hello, this is a test')
print(result)
"
```

## 📈 Performance Tips

1. **GPU Acceleration**: Ensure CUDA is properly installed
2. **Model Caching**: First TTS call loads the model (takes ~10-30s)
3. **Audio Quality**: Adjust `sample_rate` in config for quality/speed tradeoff

## 🎉 Complete!

You now have a fully functional remote access system for SOA1 that:
- ✅ Works entirely locally (no cloud)
- ✅ Uses encrypted Tailscale networking
- ✅ Provides web-based chat interface
- ✅ Supports text-to-speech responses
- ✅ Maintains complete privacy