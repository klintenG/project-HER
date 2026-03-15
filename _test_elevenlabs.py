"""Quick test of ElevenLabs with-timestamps API."""
import requests, json, base64, os

API_KEY = "22f30773422316f8e21cc92e0f3f43d3c823300974a1184ad57c2dedda4e0dd0"
VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"  # George - Warm, Captivating Storyteller

resp = requests.post(
    f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}/with-timestamps",
    headers={
        "xi-api-key": API_KEY,
        "Content-Type": "application/json",
    },
    json={
        "text": "Hello world, this is a test of word timing.",
        "model_id": "eleven_multilingual_v2",
        "output_format": "mp3_44100_128",
    },
)
print("Status:", resp.status_code)
data = resp.json()

if "alignment" in data:
    print("Has alignment data!")
    a = data["alignment"]
    print("Keys:", list(a.keys()))
    chars = a.get("characters", [])
    starts = a.get("character_start_times_seconds", [])
    ends = a.get("character_end_times_seconds", [])
    print(f"Characters: {len(chars)}, starts: {len(starts)}, ends: {len(ends)}")
    # Show word boundaries
    text = "".join(chars)
    print(f"Reconstructed text: '{text}'")
    # Print first 20 chars with times
    for i in range(min(20, len(chars))):
        print(f"  '{chars[i]}' start={starts[i]:.3f} end={ends[i]:.3f}")
elif "detail" in data:
    print("Error:", data["detail"])
else:
    print("Keys:", list(data.keys()))
    print("Response:", json.dumps(data, indent=2)[:500])

# Save audio if present
if "audio_base64" in data:
    audio_bytes = base64.b64decode(data["audio_base64"])
    out_path = "/tmp/test_elevenlabs.mp3"
    with open(out_path, "wb") as f:
        f.write(audio_bytes)
    print(f"Audio saved: {out_path} ({len(audio_bytes)} bytes)")
