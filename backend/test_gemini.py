import os
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables
load_dotenv()

# Get API key
api_key = os.getenv('GEMINI_API_KEY')

if not api_key:
    print("❌ GEMINI_API_KEY not found in environment variables")
    exit(1)

print("🔑 API Key found, testing connection...")

try:
    # Configure Gemini
    genai.configure(api_key=api_key)
    
    # Initialize model (UPDATED MODEL NAME)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    # Test prompt
    prompt = "What is the capital of France?"
    
    print(f"📝 Sending test prompt: {prompt}")
    
    # Generate response
    response = model.generate_content(prompt)
    
    print("✅ Gemini API is working!")
    print(f"🤖 Response: {response.text}")
    
except Exception as e:
    print(f"❌ Error testing Gemini API: {str(e)}")