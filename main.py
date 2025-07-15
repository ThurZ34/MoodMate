import os
import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import load_dotenv
from fastapi.responses import FileResponse


load_dotenv()

# API Keys
GROQ_API_KEY = os.getenv("GROQ_API_KEY")  # Ganti dari Together ke Groq
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-70b-versatile")  # Model Groq

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

# Validasi ENV
if not GROQ_API_KEY:
    raise Exception("GROQ_API_KEY belum diset di .env")

if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
    raise Exception("SPOTIFY_CLIENT_ID dan SPOTIFY_CLIENT_SECRET harus diset di .env")

# Setup Spotify
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET
))

# Inisialisasi FastAPI
app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Model Request
class CurhatRequest(BaseModel):
    message: str
    mood: str = "netral"  # Tambahkan mood default

class MoodRequest(BaseModel):
    mood: str

print("llama-3.1-70b-versatile", GROQ_MODEL)


# Genre berdasarkan mood (diperluas)
mood_genres = {
    "senang": "pop",
    "sedih": "acoustic",
    "galau": "r&b",
    "semangat": "rock",
    "tenang": "chill",
    "marah": "metal",
    "romantis": "romance",
    "nostalgia": "indie",
    "excited": "edm",
    "bingung": "alternative",
    "lelah": "ambient",
    "optimis": "dance",
    "cemas": "lofi",
    "bahagia": "happy",
    "netral": "pop"
}

# Motivational quotes berdasarkan mood
mood_quotes = {
    "senang": [
        "Kebahagiaan itu menular, terus sharing positive vibes-mu! ✨",
        "Moment bahagia kayak gini harus dijaga dan disyukuri ya! 💫",
        "Seneng banget liat kamu happy, keep that energy! 🌟"
    ],
    "sedih": [
        "Gak apa-apa nangis, itu juga bentuk kekuatan loh 💪",
        "Sedih itu wajar, yang penting jangan lupa bangkit ya 🌈",
        "Every storm runs out of rain, ini cuma phase doang kok 🌤️"
    ],
    "galau": [
        "Kadang kita perlu sendiri biar ngerti arti ditemani 🤗",
        "Galau itu tandanya kamu care sama hidup kamu, it's okay 💭",
        "Confusion is temporary, clarity will come soon 🌅"
    ],
    "semangat": [
        "Energy kamu tuh inspiring banget, go get 'em! 🔥",
        "Semangat kamu bikin aku juga excited, let's goooo! 🚀",
        "Vibe kamu lagi on fire, manfaatin momentum ini! ⚡"
    ],
    "tenang": [
        "Inner peace vibes detected, enjoy this moment 🧘‍♀️",
        "Ketenangan itu luxury di zaman sekarang, appreciate it 🌸",
        "Peaceful mind, peaceful life. You're doing great! 🕊️"
    ],
    "marah": [
        "Marah itu normal, yang penting channeling-nya yang benar 🌊",
        "Anger is just passion with nowhere to go, find your way 🎯",
        "Take a deep breath, kamu pasti bisa handle ini 💨"
    ]
}

# Helper Spotify Track
def extract_tracks(results):
    tracks = []
    for item in results['tracks']['items']:
        track_info = {
            "name": item['name'],
            "artist": item['artists'][0]['name'],
            "url": item['external_urls']['spotify'],
            "image": item['album']['images'][0]['url'] if item['album']['images'] else None
        }
        tracks.append(track_info)
    return tracks

# Helper function untuk call Groq API
def call_groq_api(messages, temperature=0.7, max_tokens=256):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "top_p": 1,
        "stream": False
    }
    
    try:
        response = requests.post("https://api.groq.com/openai/v1/chat/completions", 
                               headers=headers, json=payload)
        
        if response.status_code != 200:
            return None, f"API Error: {response.status_code}"
            
        result = response.json()
        reply = result["choices"][0]["message"]["content"].strip()
        return reply, None
        
    except Exception as e:
        return None, str(e)

# Endpoint: /pilih-mood
@app.post("/pilih-mood")
def pilih_mood(data: MoodRequest):
    selected_mood = data.mood.lower()
    genre = mood_genres.get(selected_mood, "pop")
    
    # Ambil quote random berdasarkan mood
    import random
    quotes = mood_quotes.get(selected_mood, mood_quotes["senang"])
    selected_quote = random.choice(quotes)
    
    try:
        # Cari lagu berdasarkan genre dan mood
        search_queries = [
            f"genre:{genre}",
            f"mood {selected_mood}",
            f"{genre} {selected_mood}"
        ]
        
        all_tracks = []
        for query in search_queries:
            try:
                results = sp.search(q=query, type="track", limit=5)
                tracks = extract_tracks(results)
                all_tracks.extend(tracks)
            except:
                continue
        
        # Remove duplicates dan ambil 6 teratas
        seen = set()
        unique_tracks = []
        for track in all_tracks:
            track_id = (track['name'], track['artist'])
            if track_id not in seen:
                seen.add(track_id)
                unique_tracks.append(track)
                if len(unique_tracks) >= 6:
                    break
                    
        recommendations = unique_tracks
        
    except Exception as e:
        print(f"Spotify error: {e}")
        recommendations = []
    
    return {
        "mood": selected_mood,
        "quote": selected_quote,
        "recommendations": recommendations
    }

# Endpoint: /curhat-lanjut
@app.post("/curhat-lanjut")
def curhat_lanjut(data: CurhatRequest):
    user_text = data.message
    current_mood = data.mood.lower()
    
    messages = [
        {
            "role": "system",
            "content": (
                "Kamu adalah MoodMate, AI teman bagi gen z yang empathetic dan supportive. "
                "Karaktermu ramah, pengertian, dan bisa relate dengan perasaan anak muda. "
                "Berikan respon yang:\n"
                "1. Empathetic dan validating\n"
                "2. Menggunakan bahasa gaul anak muda Indonesia\n"
                "3. Supportive tapi realistis\n"
                "4. Panjang respon 2-4 kalimat\n"
                "5. Boleh pakai emoji yang relevan\n"
                "6. Jangan judge, fokus pada support\n"
                "7. Jawab sesuai mood mereka jika sedih dan yang lainnya berarti curhat jika berkaitan dengan semangat, senang, optimis, excited maka jawab mereka dengan semangat juga\n\n"
                "Contoh gaya bahasa:\n"
                "- 'Aku ngerti banget gimana rasanya...'\n"
                "- 'That's totally valid sih...'\n"
                "- 'Kamu udah strong banget loh...'\n"
                "- 'It's okay to feel that way...'\n"
                "Jangan gunakan format JSON, langsung kasih response natural aja."
            )
        },
        {
            "role": "user",
            "content": f"Mood aku lagi {current_mood} dan aku mau curhat: {user_text}"
        }
    ]
    
    reply, error = call_groq_api(messages, temperature=0.8, max_tokens=512)
    
    if error:
        return {
            "response": "Maaf ya, lagi ada gangguan teknis. Tapi aku tetap di sini buat dengerin kamu kok 🤗"
        }
    
    return {
        "response": reply
    }

# Endpoint untuk analisis mood dari teks (optional)
@app.post("/analyze-mood")
def analyze_mood(data: CurhatRequest):
    user_text = data.message
    
    messages = [
        {
            "role": "system",
            "content": (
                "Kamu adalah mood analyzer yang bisa detect mood dari teks. "
                "Berikan response dalam format JSON:\n"
                "{\"mood\": \"detected_mood\", \"confidence\": 0.85, \"explanation\": \"penjelasan singkat\"}\n\n"
                "Mood options: senang, sedih, galau, semangat, tenang, marah, romantis, nostalgia, excited, bingung, lelah, optimis, cemas, bahagia, netral\n"
                "Confidence: 0.0-1.0\n"
                "Explanation: 1 kalimat kenapa mood ini terdeteksi"
            )
        },
        {
            "role": "user",
            "content": f"Analyze mood dari teks ini: {user_text}"
        }
    ]
    
    reply, error = call_groq_api(messages, temperature=0.3, max_tokens=256)
    
    if error:
        return {
            "mood": "netral",
            "confidence": 0.5,
            "explanation": "Gagal menganalisis mood"
        }
    
    try:
        # Clean up response jika ada backticks
        if reply.startswith("```"):
            reply = reply.strip("` \n")
            if reply.lower().startswith("json"):
                reply = reply[4:].strip()
        
        parsed = json.loads(reply)
        return parsed
        
    except json.JSONDecodeError:
        return {
            "mood": "netral",
            "confidence": 0.5,
            "explanation": "Format response tidak valid"
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)