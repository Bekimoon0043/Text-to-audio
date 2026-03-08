# Amharic Text-to-Speech Service

A simple Flask-based TTS service supporting Amharic (and other languages via gTTS). Deployable for free on Render.

## Features
- Web interface to enter text and hear the result.
- REST API endpoint `/api/tts` for integration with n8n or other tools.
- Returns MP3 audio stream.

## API Usage
**Endpoint:** `POST /api/tts`  
**Content-Type:** `application/json` or `application/x-www-form-urlencoded`  
**Parameters:**
- `text` (required): The text to convert.
- `lang` (optional): Language code (default `am` for Amharic).

**Example (JSON):**
```bash
curl -X POST https://your-app.onrender.com/api/tts \
  -H "Content-Type: application/json" \
  --data '{"text":"ሰላም", "lang":"am"}' \
  --output speech.mp3
