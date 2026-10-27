import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

if not os.getenv("GEMINI_API_KEY"):
    raise ValueError("GEMINI_API_KEY is missing from .env")

client = genai.Client()

response = client.models.embed_content(
    model="gemini-embedding-2",
    contents=(
        "title: Library Notice | "
        "text: The library will close at 5 PM today."
    ),
    config=types.EmbedContentConfig(
        output_dimensionality=768
    ),
)

if not response.embeddings:
    raise RuntimeError("No embedding was returned.")

vector = response.embeddings[0].values

print("Embedding generated successfully!")
print("Vector dimensions:", len(vector))
print("First five values:", vector[:5])