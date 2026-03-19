from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

import pandas as pd
import io
import os
import matplotlib.pyplot as plt

app = FastAPI()

app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/analyze")
def analyze_page():
    return RedirectResponse(url="/")
    
@app.post("/analyze", response_class=HTMLResponse)
async def analyze(request: Request, file: UploadFile = File(...)):
    contents = await file.read()

    try:
        text = contents.decode("utf-8")
    except UnicodeDecodeError:
        text = contents.decode("cp932")

    df = pd.read_csv(io.StringIO(text))
    total = len(df)

    # ===== 感情抽出 =====
    positive_words = ["美味しい", "最高", "良い", "丁寧", "また来たい", "満足", "親切"]
    negative_words = ["遅い", "高い", "まずい", "冷たい", "汚い", "最悪", "不満"]

    pos_count = 0
    neg_count = 0
    neu_count = 0

    for text in df["review_text"]:
        text = str(text)

        pos_hit = any(word in text for word in positive_words)
        neg_hit = any(word in text for word in negative_words)

        if pos_hit and not neg_hit:
            pos_count += 1
        elif neg_hit and not pos_hit:
            neg_count += 1
        elif pos_hit and neg_hit:
            neu_count += 1  # 両方ある → ニュートラル扱い
        else:
            neu_count += 1

    # ===== キーワード抽出 =====
    keyword_candidates = ["味", "料理", "接客", "店員", "提供", "雰囲気", "価格", "値段", "店内"]

    keyword_counts = {}

    for keyword in keyword_candidates:
        count = 0
        for text in df["review_text"]:
            text = str(text)
            if keyword in text:
                count += 1
        keyword_counts[keyword] = count

    sorted_keywords = sorted(
        keyword_counts.items(),
        key=lambda x: x[1],
        reverse=True
    )

    # ===== グラフ作成 =====
    labels = ["Positive", "Negative", "Neutral"]
    values = [pos_count, neg_count, neu_count]

    plt.figure(figsize=(6, 4))
    plt.bar(labels, values)
    plt.title("Sentiment Analysis")
    plt.xlabel("Sentiment")
    plt.ylabel("Count")
    plt.tight_layout()

    chart_path = "app/static/charts/sentiment_chart.png"
    plt.savefig(chart_path)
    plt.close()

    return templates.TemplateResponse(
    "result.html",
        {
            "request": request,
            "total": total,
            "pos": pos_count,
            "neg": neg_count,
            "neu": neu_count,
            "keywords": sorted_keywords
        }
    )