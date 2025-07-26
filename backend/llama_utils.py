import threading
from llama_cpp import Llama

# Thread lock to avoid simultaneous llama() calls
llm_lock = threading.Lock()

# Load LLaMA model
llm = Llama(
    model_path="models/llama-3.2-3b-instruct-q3_k_l.gguf",
    n_ctx=512,
    n_threads=6,
    n_gpu_layers=0,
    verbose=False
)

# ------------------------- #
# LLaMA Wrapper
# ------------------------- #

def generate_llama_response(prompt: str, max_tokens=64):
    try:
        with llm_lock:
            output = llm(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=0.1,
                top_p=0.9,
                stop=["\n", "User:", "Answer:"]
            )
        return output["choices"][0]["text"].strip()
    except Exception as e:
        print("[LLaMA ERROR]:", str(e))
        return None  # Trigger fallback
        

# ------------------------- #
# Tone Classifier
# ------------------------- #

def classify_email_tone(email_text: str) -> str:
    prompt = (
        "You are a tone classifier. Respond with a single word that describes the emotional tone of the email.\n"
        "Choose ONLY from the following: polite, urgent, neutral, formal, angry, friendly, apologetic, "
        "appreciative, sarcastic, confused, demanding, encouraging, threatening, dismissive.\n\n"

        "Email: Please help me with the budget document.\nAnswer: polite\n"
        "Email: Please help me now, I need it urgently!\nAnswer: urgent\n"
        "Email: Please leave me alone.\nAnswer: dismissive\n"
        "Email: What the hell were you thinking?\nAnswer: angry\n"
        "Email: You're amazing, thank you so much!\nAnswer: appreciative\n"
        "Email: I'm sorry this happened. I'll fix it.\nAnswer: apologetic\n"
        "Email: Can we look into this next week?\nAnswer: neutral\n"
        "Email: Let's grab coffee when you're free\nAnswer: friendly\n"
        "Email: Just great. Another issue to deal with.\nAnswer: sarcastic\n"
        "Email: Why wasn't I told about this earlier?\nAnswer: confused\n"
        "Email: I expect a report on my desk by 9am. No excuses.\nAnswer: demanding\n"
        "Email: You've got this! Keep going!\nAnswer: encouraging\n"
        "Email: If you don't respond, I will escalate this.\nAnswer: threatening\n"
        "Now classify the tone of this email:\n"
        f"Email: {email_text.strip()}\nAnswer:"
    )


    result = generate_llama_response(prompt, max_tokens=8)
    if result:
        result = result.lower()
        print("[Tone Raw]:", repr(result))
        tones = [
            "polite", "urgent", "neutral", "formal", "angry", "friendly", "apologetic",
            "appreciative", "sarcastic", "confused", "demanding", "encouraging",
            "threatening", "dismissive"
        ]

        for tone in tones:
            if tone in result:
                return tone


        return f"unknown ({result})"

    # 🔁 Fallback: Keyword-based tone detection
    text = email_text.lower()
    if any(word in text for word in ["sorry", "apologize", "inconvenience"]):
        return "apologetic"
    elif any(word in text for word in ["great job", "well done", "thank you", "appreciate"]):
        return "appreciative"
    elif any(word in text for word in ["what now", "again?", "of course", "just great"]):
        return "sarcastic"
    elif any(word in text for word in ["looking forward", "can't wait", "excited"]):
        return "friendly"
    elif any(word in text for word in ["why", "how come", "wasn't it", "unclear"]):
        return "confused"
    elif any(word in text for word in ["do this", "no excuses", "now"]):
        return "demanding"
    elif any(word in text for word in ["you can do it", "keep going", "don't give up"]):
        return "encouraging"
    elif any(word in text for word in ["consequences", "last warning", "legal action"]):
        return "threatening"
    elif any(word in text for word in ["whatever", "don't care", "not my problem"]):
        return "dismissive"


# ------------------------- #
# Spam Detector
# ------------------------- #

def detect_spam(email_text: str) -> bool:
    prompt = (
        "You are a spam detector. Respond only with 'yes' or 'no'.\n\n"
        "Email: You've won a free prize! Click this link to claim.\nAnswer: yes\n"
        "Email: Let's schedule a meeting for next week.\nAnswer: no\n"
        f"Email: {email_text.strip()}\nAnswer:"
    )

    result = generate_llama_response(prompt, max_tokens=5)
    if result:
        result = result.lower()
        print("[Spam Raw]:", repr(result))
        return "yes" in result

    # 🔁 Fallback: Keyword-based spam detection
    spam_keywords = ["click here", "free", "prize", "congratulations", "winner", "claim", "urgent offer"]
    return any(word in email_text.lower() for word in spam_keywords)

def summarize_email(email_text: str) -> str:
    prompt = (
        "You are an expert email summarizer. Summarize the following email in 1-2 sentences:\n\n"
        f"Email: {email_text.strip()}\n\n"
        "Summary:"
    )
    result = generate_llama_response(prompt, max_tokens=100)
    if result:
        print("[Summary Raw]:", repr(result))
        return result.strip()
    return "Summary unavailable."