# --- The "AI Studio Manager" Back-End ---
#
# This server is a "manager" that hires an "AI expert" (Gemini)
# for every conversion job. It's flexible and scalable.
#
# To run this, you must install Flask, Flask-CORS, and httpx:
# pip install Flask flask-cors httpx
#
# Then run the server:
# python server.py
#
# This server, in turn, calls the Gemini API, so it must
# be running in an environment where it can make outbound requests.

import json
import httpx  # A modern, async-friendly HTTP client (like 'requests')
import asyncio # For handling async API calls

try:
    from flask import Flask, request, jsonify
    from flask_cors import CORS
except ImportError:
    print("Flask/CORS not found. Please run 'pip install Flask flask-cors'")
    exit(1)

# -----------------------------------------------------------------
# --- The Flask Server "Wrapper" ---
# -----------------------------------------------------------------

app = Flask(_name_)
# CORS is needed to allow the HTML file to call this server
CORS(app) 

# We'll use a single, shared, async-capable HTTP client
# This is much more efficient than creating a new one for every request
client = httpx.AsyncClient()


# -----------------------------------------------------------------
# --- The AI "Freelancer" (Gemini API Call) ---
# -----------------------------------------------------------------

async def call_gemini_converter(code: str, from_lang: str, to_lang: str) -> str:
    """
    Calls the Gemini API to perform the professional conversion.
    This function contains the "contract" (system prompt) for the AI.
    """
    
    # The API key is handled by the environment (e.g., Google Cloud Run)
    # In a local test, you might need to set this.
    api_key = "AIzaSyANAjl4KV2KvU_xJxCANWtfVnt2yJd8eSk" # Handled by the environment
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent?key={api_key}"

    # --- THIS IS THE "PROFESSIONAL CONTRACT" (SYSTEM PROMPT) ---
    # We are programmatically inserting all the user's advanced requirements
    # into this prompt.
    system_prompt = f"""
You are an expert-level programmer and code transpiler. Your task is to convert the given {from_lang} code into {to_lang}.

Follow these rules PERFECTLY:

1.  *Strict Output:* You MUST output ONLY the raw, complete, and runnable {to_lang} code.
2.  *No Explanations:* Do NOT include any explanations, apologies, introductions, or markdown formatting like {to_lang.lower()} ... .
3.  *Preserve Logic:* The converted code must maintain the exact same logic, functionality, and program flow as the original.
4.  *Make it Idiomatic:* The converted code must be "idiomatic" for {to_lang}. For example, use standard library features, naming conventions (e.g., camelCase vs. snake_case), and data structures of {to_lang}.
5.  *Map Libraries:* Where possible, map standard library functions from {from_lang} to their equivalents in {to_lang}.
6.  *Handle Errors (CRITICAL):*
    * If a feature in {from_lang} (e.g., a specific library like 'pandas') has NO direct equivalent in {to_lang}, you MUST NOT invent a solution.
    * Instead, you MUST leave the original line of code as-is (or a minimal placeholder) and add a DETAILED code comment directly above it, prefixed with "// TODO: [UNSUPPORTED_FEATURE]".
    * This comment must explain why it's unsupported and what a human developer should do manually.
7.  *Preserve Comments:* All existing comments in the code must be preserved and translated if necessary.

Failure to adhere to the "Strict Output" rule (Rule 1) will result in failure.
"""

    user_prompt = f"Convert the following {from_lang} code to {to_lang}:\n\n{code}"

    payload = {
        "contents": [{"parts": [{"text": user_prompt}]}],
        "systemInstruction": {"parts": [{"text": system_prompt}]},
    }

    try:
        # We use the shared 'client' to make the async call
        response = await client.post(api_url, json=payload, timeout=60.0)

        if response.status_code == 429:
            # Handle rate limiting
            return "// SERVER_ERROR: The API is busy. Please try again in a moment."

        response.raise_for_status() # Raise an error for bad responses (4xx, 5xx)

        result = response.json()
        
        candidate = result.get('candidates', [{}])[0]
        text_part = candidate.get('content', {}).get('parts', [{}])[0].get('text', None)

        if text_part is None:
            # This handles cases where the AI's response was "empty" or "unsafe"
            raise ValueError(f"AI returned an empty or invalid response. Safety: {candidate.get('finishReason')}")
            
        return text_part.strip()

    except httpx.ReadTimeout:
        return f"// SERVER_ERROR: The conversion request timed out. The {from_lang} code might be too complex."
    except Exception as e:
        print(f"SERVER ERROR: An error occurred calling Gemini: {e}")
        return f"// SERVER_ERROR: An internal error occurred. {e}"

# -----------------------------------------------------------------
# --- The API Endpoint (The "Front Office") ---
# -----------------------------------------------------------------

@app.route('/convert', methods=['POST'])
async def handle_conversion():
    """
    This is the "API Endpoint" (the "phone number").
    Note: It is 'async def' to allow it to 'await' the Gemini call
    without blocking the whole server.
    """
    print("\n--- SERVER: Received a new /convert request! ---")
    
    # Get the JSON data from the front-end's "fetch" request
    data = request.json
    
    try:
        code = data['code']
        from_lang = data['from_lang']
        to_lang = data['to_lang']
        
        print(f"SERVER: Job accepted. Converting {from_lang} to {to_lang}...")
        
        # --- This is the key! ---
        # The server "hires" the AI by awaiting the async function.
        # The 'pipeline' is now just this one powerful function.
        converted_code = await call_gemini_converter(code, from_lang, to_lang)
        
        print("SERVER: AI conversion complete. Sending result to client.")
        
        # Send the result back to the front-end as JSON
        return jsonify({"converted_code": converted_code})
    
    except Exception as e:
        print(f"SERVER ERROR: {e}")
        # Send a structured error message back to the front-end
        return jsonify({"error": str(e)}), 400

# This makes the server run when you execute 'python server.py'
if _name_ == '_main_':
    print("Starting the AI Studio Manager server on http://127.0.0.1:5000")
    # This runs the Flask app
    app.run(debug=True, port=5000)
