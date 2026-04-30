from fastapi import FastAPI, UploadFile, File, Request, Body
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from openai import OpenAI

import pandas as pd
import io
import os
import matplotlib.pyplot as plt

css_version = int(os.path.getmtime("app/static/css/style.css"))

app = FastAPI()

app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    css_version = int(os.path.getmtime("app/static/css/style.css"))
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "css_version": css_version,
        }
    )

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

    # ===== トップキーワード =====
    top_keyword = sorted_keywords[0][0] if sorted_keywords else None

    # ===== 感情分析棒グラフ作成 =====
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

    # ===== ポジネガ割合円グラフ作成 =====
    plt.figure(figsize=(5, 5))
    plt.pie(
        [pos_count, neg_count],
        labels=["Positive", "Negative"],
        autopct="%1.1f%%"
    )
    plt.title("Sentiment Ratio")
    plt.tight_layout()

    pie_chart_path = "app/static/charts/pie_chart.png"
    plt.savefig(pie_chart_path)
    plt.close()

    # ===== 分析コメント =====
    if pos_count > neg_count:
        comment = "全体的に評価は良好です。"
    elif neg_count > pos_count:
        comment = "ネガティブな意見がやや目立ちます。改善ポイントの確認が必要です。"
    else:
        comment = "評価は拮抗しており、良い点と改善点の両方が見られます。"

    top_keyword = None
    for k, v in sorted_keywords:
        if v > 0:
            top_keyword = k
            break

    if top_keyword == "接客":
        comment += " 特に接客に関する意見が多く見られます。"
    elif top_keyword in ["味", "料理"]:
        comment += " 特に料理・味に関する意見が多く見られます。"
    elif top_keyword == "提供":
        comment += " 提供スピードに関する意見が多く見られます。"
    elif top_keyword in ["価格", "値段"]:
        comment += " 価格に関する意見が多く見られます。"
    elif top_keyword in ["雰囲気", "店内"]:
        comment += " 店内の雰囲気に関する意見が多く見られます。"

    # ===== 評価 =====
    score = (pos_count * 5 + neu_count * 3 + neg_count * 1) / total
    score = round(score, 1)

    # ===== AIチャット用サマリー =====
    summary = f"""
総レビュー数: {total}
ポジティブ: {pos_count}
ネガティブ: {neg_count}
ニュートラル: {neu_count}
主要キーワード: {', '.join([k for k, v in sorted_keywords[:3]])}
総合評価: {score} / 5
分析コメント: {comment}
"""

    return templates.TemplateResponse(
    "result.html",
        {
            "css_version": css_version,
            "request": request,
            "total": total,
            "pos": pos_count,
            "neg": neg_count,
            "neu": neu_count,
            "keywords": sorted_keywords,
            "comment": comment,
            "score": score,
            "top_keyword": top_keyword,
            "summary": summary,
        }
    )

# ===== AIチャット =========================
client = OpenAI()

@app.post("/chat")
async def chat(summary: str = Body(...), question: str = Body(...), character: str = Body("default")):
    if not summary.strip() or not question.strip():
        return JSONResponse(
            status_code=400,
            content={"error": "入力が空です"}
        )

    character_prompt = {
        "default": """
            あなたは冷静で論理的な分析アシスタントです。
            以下のルールで回答してください：
            ・簡潔で分かりやすく説明する
            ・結論 → 理由の順で話す
            ・無駄な表現は避ける
            分析結果をもとに、正確に回答してください。
            """,
        "friendly": """
            あなたはフレンドリーな友人です。
            敬語は使わず、カジュアルに話してください。
            以下のルールで回答してください：
            ・短めの文章でテンポよく話す
            ・少しリアクションを入れる
            ・難しく説明しない
            軽く会話するように、飲食店の特徴を伝えてください。
            """,
        "butler": """
            あなたは落ち着いた執事です。
            丁寧で上品な言葉遣いで話してください。
            以下のルールで回答してください：
            ・ゆったりとした丁寧な文章
            ・論理的に順序立てて説明する
            ・感情を強く出しすぎない
            安心感のある口調で、飲食店の分析を説明してください。
            """,
        "host": """
            あなたは自信があり人を惹きつけるホストです。
            敬語は使わず、フランクで少しキザな口調で話してください。
            以下のルールで回答してください：
            ・文章は短めに区切る
            ・説明しすぎない
            ・会話のようなテンポで話す
            ・少し相手を特別扱いする
            ・最後に一言、相手に話しかける
            軽く語るように、飲食店の魅力や改善点を伝えてください。
            """,
        "tsundere": """
            あなたはツンデレな性格です。
            素直じゃない言い方をしつつ、最後は少しだけ優しさを見せます。
            以下のルールで回答してください：
            ・最初は否定やそっけない言い方をする
            ・説明はちゃんとする
            ・最後に少しだけフォローする
            ・敬語は使わない
            飲食店の分析を、ぶっきらぼうに伝えてください。
            """,
    }

    try:
        prompt = f"""
{character_prompt.get(character, character_prompt["default"])}

以下は飲食店レビュー分析の結果です。

{summary}

この結果をもとに質問に答えてください。

質問: {question}
"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        return {
            "answer": response.choices[0].message.content
        }

    except Exception as e:
        print("CHAT ERROR:", e)
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )        