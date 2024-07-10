from youtube_transcript_api import YouTubeTranscriptApi
from fastapi import FastAPI, Request
import os
import json
import requests

UPSTREAM_API_ROOT_URL = "https://api-inference.huggingface.co/models"

try:
    API_KEY_FROM_ENV = os.environ["API_KEY"]
except KeyError:
    print(
        'upstream API_KEY not set in Vercel environment variables ( "https://vercel.com/docs/projects/environment-variables" )'
    )
    exit(0)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.3",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Authorization": f"Bearer {API_KEY_FROM_ENV}",
    "Referer": "https://slcm.manipal.edu/FacultyAssessment.aspx",
    "Connection": "keep-alive",
    "Cookie": "ASP.NET_SessionId=",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Pragma": "no-cache",
    "Cache-Control": "no-cache",
    "TE": "trailers",
}

PARAMETERS = {
    "min_length": 30,
    "do_sample": False,
    "use_cache": False,
}


app = FastAPI()


@app.get("/")
async def root():
    return {
        "message": "Use endpoint /transcript/{video_id}",
        "docs": "To access docs, use endpoint /docs",
    }


@app.get("/transcript/{video_id}")
def get_transcript_from_video_id(video_id: str):
    # video_id = "Z6nkEZyS9nA"
    transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
    complete_transcript = ""
    for transcript in transcript_list:
        text = transcript["text"]
        complete_transcript += text + " "

        # Uncomment this if you want the transcript in a file
        # with open(f"transcript_{video_id}.txt", "a") as opf:
        #     opf.write(text + "\n")

    # Ensure transcript only contains utf-8 chars
    complete_transcript = complete_transcript.encode("utf-8", errors="ignore").decode(
        "utf-8"
    )
    return {"transcript": complete_transcript}


@app.post("/summary")
async def get_summary_from_upstream(request: Request):
    ##### JSON validation start #####

    try:
        body = await request.json()
    except json.decoder.JSONDecodeError:
        return {"success": False, "status": 400, "msg": "JSON decode Error"}

    keys = body.keys()

    min_length = (
        body["min_length"]
        if "min_length" in keys and body["min_length"]
        else PARAMETERS["min_length"]
    )

    if "model" not in keys:
        return {"success": False, "status": 400, "msg": '"model" field is mandatory'}

    if "text" not in keys:
        return {"success": False, "status": 400, "msg": '"text" field is mandatory'}

    model = body["model"]
    text = body["text"]

    if (
        not isinstance(min_length, int)
        or not isinstance(model, str)
        or not isinstance(text, str)
        or not model
        or not text
    ):
        return {"success": False, "status": 400, "msg": "Invalid input"}

    if model[0] == "/":
        return {
            "success": False,
            "status": 400,
            "msg": 'First character of "model" must be alphanumeric',
        }

    if min_length > 1000 or len(model) > 200 or len(text) > 2000:
        return {"success": False, "status": 413, "msg": "Input too long"}

    ##### JSON validation end #####

    PARAMETERS["min_length"] = min_length

    r = requests.post(
        f"{UPSTREAM_API_ROOT_URL}/{model}",
        headers=HEADERS,
        json={"inputs": text, "parameters": PARAMETERS},
    )

    try:
        response_json = json.loads(r.text)
    except json.decoder.JSONDecodeError:
        return {
            "success": False,
            "status": 503,
            "msg": "JSON decode error after upstream response",
        }

    if (
        not isinstance(response_json, list)
        or not len(response_json)
        or (
            not isinstance(response_json[0], dict)
            or not "summary_text" in response_json[0].keys()
        )
    ):
        return {
            "success": False,
            "status": r.status_code,
            "msg": "upstream error",
            "data": response_json,
        }

    return {"success": True, "status": r.status_code, "summary": response_json}


# To run
# ```uvicorn app:app --reload```
# also rename main.py to app.py for localhost running
