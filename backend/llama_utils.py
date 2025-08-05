import os
from dotenv import load_dotenv
from groq import Groq

# ------------------------- #
# Groq Model Setup
# ------------------------- #

# Make sure you set your Groq API key in the environment:
# export GROQ_API_KEY="your_api_key_here"
# or in Windows:
# setx GROQ_API_KEY "your_api_key_here"
load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API"))

# ------------------------- #
# Groq Wrapper
# ------------------------- #

def generate_llama_response(prompt: str, max_tokens=64):
    try:
        response = client.chat.completions.create(
            model="llama3-8b-8192",  # You can change to llama3-70b if needed
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=max_tokens,
            top_p=0.9
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("[Groq ERROR]:", str(e))
        return None


# ------------------------- #
# Tone Classifier (Multi-tone)
# ------------------------- #

def classify_email_tone(email_text: str) -> str:
    prompt = (
        "You are a tone classifier. Respond with the main emotional tone present in the email, "
        "only 1 from the following list: polite, urgent, neutral, formal, "
        "angry, friendly, apologetic, appreciative, sarcastic, confused, demanding, encouraging, "
        "threatening, dismissive.\n"
        "Do not explain, just name the main tone.\n\n"
        f"Email: {email_text.strip()}\nAnswer:"
    )

    result = generate_llama_response(prompt, max_tokens=16)
    if result:
        result = result.lower()
        print("[Tone Raw]:", repr(result))
        tones = [
            "polite", "urgent", "neutral", "formal", "angry", "friendly", "apologetic",
            "appreciative", "sarcastic", "confused", "demanding", "encouraging",
            "threatening", "dismissive"
        ]

        detected = [tone for tone in tones if tone in result]
        if detected:
            return ", ".join(detected)

    # Fallback keyword-based tone detection
    fallback_tones = []
    text = email_text.lower()
    if any(w in text for w in ["sorry", "apologize", "inconvenience"]):
        fallback_tones.append("apologetic")
    if any(w in text for w in ["great job", "well done", "thank you", "appreciate"]):
        fallback_tones.append("appreciative")
    if any(w in text for w in ["what now", "again?", "of course", "just great"]):
        fallback_tones.append("sarcastic")
    if any(w in text for w in ["looking forward", "can't wait", "excited"]):
        fallback_tones.append("friendly")
    if any(w in text for w in ["why", "how come", "wasn't it", "unclear"]):
        fallback_tones.append("confused")
    if any(w in text for w in ["do this", "no excuses", "now"]):
        fallback_tones.append("demanding")
    if any(w in text for w in ["you can do it", "keep going", "don't give up"]):
        fallback_tones.append("encouraging")
    if any(w in text for w in ["consequences", "last warning", "legal action"]):
        fallback_tones.append("threatening")
    if any(w in text for w in ["whatever", "don't care", "not my problem"]):
        fallback_tones.append("dismissive")
    
    if fallback_tones:
        return ", ".join(set(fallback_tones))

    return "neutral"


# ------------------------- #
# Spam Detector (Tone-Aware)
# ------------------------- #

def detect_spam(email_text: str) -> bool:
    """
    Returns True if email is spam, False otherwise.
    Uses Groq LLaMA intelligence only — no keyword rules.
    """

    prompt = f"""
You are an expert spam, phishing, and scam detector for emails.
Classify if the email below is spam.

Spam includes:
- Any scam, phishing, or fraudulent attempt
- Requests for sensitive personal or financial information
- Fake offers, contests, or prizes
- Marketing emails without consent
- Anything deceptive or harmful

Return your answer in EXACTLY one word: 'yes' or 'no'.

Email:
\"\"\"{email_text.strip()}\"\"\"
Answer:
    """

    result = generate_llama_response(prompt, max_tokens=5)
    if not result:
        return False  # default safe value

    answer = result.strip().lower()
    print("[Spam Raw]:", repr(answer))
    return answer.startswith("yes")


# ------------------------- #
# Summarizer
# ------------------------- #

def summarize_email(email_text: str) -> str:
    prompt = (
        "You are an expert email summarizer. Summarize the following email using easy vocabulary under 30 and just state the summary nothing else:\n\n"
        f"Email: {email_text.strip()}\n\n"
        "Summary:"
    )
    result = generate_llama_response(prompt, max_tokens=100)
    if result:
        print("[Summary Raw]:", repr(result))
        return result.strip()
    return "Summary unavailable."

def rewrite_email_tone(text: str, tone: str) -> str:
    prompt = (
        f"You are an expert email editor. Rewrite the following email text to have a {tone} tone. "
        "Keep the core message and meaning the same, but adjust the phrasing, vocabulary, and nuance. "
        "Respond ONLY with the rewritten email body, and nothing else.\n\n"
        f"Original Text: \"{text.strip()}\"\n\n"
        f"Rewritten Text with a {tone} tone also just give the rewritten text no need to say that you have rewritten it and make sure that it is the same word count"
    )
    # Give the model more tokens for rewriting longer text
    result = generate_llama_response(prompt, max_tokens=512)
    print(result)
    if result[0] == '"' and result[-1]=='"':
        return result[1:-1]
    return result if result else "Could not rewrite the text."