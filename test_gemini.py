from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client()

try:
    response = client.models.generate_content(
        model="gemini-3.1-flash-lite",
        contents="Reply with exactly: Gemini connection successful."
    )
    print(response.text)

except Exception as e:
    print(f"API test failed: {e}")