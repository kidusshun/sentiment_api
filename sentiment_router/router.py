from fastapi import APIRouter
from pydantic import BaseModel
from sentiment_router.utils import industries
import requests
from datetime import datetime, timedelta
from config import MySettings
from firecrawl import FirecrawlApp
from openai import OpenAI
from newspaper import Article

client = OpenAI(
    api_key=MySettings.GEMINI_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

class ReportSentiment(BaseModel):
    report: str
    sentiment: str

app = FirecrawlApp(api_key=MySettings.FIRE_CRAWL_API_KEY)

sentiment_router = APIRouter()

class SentimentRequest(BaseModel):
    text: str

system_message = """
You are assigned the task of analyzing a large amount of news articles related to an industry or market segment. 
You have two tasks
One of your task is to generate a comprehensive report on the text for investors that gives insights into the current state of the industry.
Tailor the report to be suitable for investorslooking and searching for opportunities, focusing on key trends, challenges, and opportunities in the industry. 
Secondly, You need to analyze and extract and rephrase sentences from the text to be passed to a sentiment analysis model. Make sure to extract only the most relevant sentences that capture the essence and sentiment of the news articles.

Make sure to make the report markdown formatted properly with headings, bullet points, and other formatting elements to enhance readability.
Don't use markdown for the sentiment text, just return the sentences as plain text.
"""

def fetch_news_articles(query: str, from_date, to_date, page=1, page_size=100, search_in_title=False):
    url = (
        "https://newsapi.org/v2/everything"
        f"?q={query}"
        f"&from={from_date}&to={to_date}"
        f"{'&searchIn=title' if search_in_title else ''}"
        "&sortBy=popularity"
        f"&pageSize={page_size}"
        f"&page={page}"
        f"&apiKey={MySettings.NEWS_API_KEY}"
    )
    response = requests.get(url)
    if response.status_code != 200:
        return None, {"error": f"Failed to fetch news: {response.status_code} - {response.text}"}
    data = response.json()
    articles = data.get("articles", [])
    if not articles:
        return None, {"error": "No articles found for the given query."}
    return articles, None

def extract_titles(articles):
    return [article["title"] for article in articles]

def extract_urls_titles(articles):
    return [(article["url"], article["title"]) for article in articles]

def scrape_articles(urls):
    text_corpus = ""
    for url in urls:
        try:
            res = app.scrape_url(url, formats=['markdown'])
            if res.success: # type: ignore
                text_corpus += res.markdown + "\n" # type: ignore
        except Exception as e:
            print(f"Error scraping {url}: {e}")
            continue
    return text_corpus

def scrape_article_with_newspaper(urls):
    text_corpus = ""
    for url in urls:
        try:
            article = Article(url)
            article.download()
            article.parse()
            text_corpus += article.text
        except Exception as e:
            print(f"Error scraping {url} with newspaper: {e}")
    return text_corpus

def generate_gemini_report(text_corpus):
    completion = client.beta.chat.completions.parse(
        model="gemini-2.0-flash",
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": text_corpus},
        ],
        response_format=ReportSentiment,
    )
    return completion.choices[0].message.parsed

def analyze_sentiment(sentiment_text):
    sentiment_url = "https://kidusshun-buildspace-sentiment.hf.space/sentiment"
    sentiment_response = requests.post(
        sentiment_url,
        json={"text": sentiment_text},
    )
    if sentiment_response.status_code != 200:
        return None, {"error": f"Failed to analyze sentiment: {sentiment_response.status_code} - {sentiment_response.text}"}
    return sentiment_response.json(), None

@sentiment_router.post("/startup/sentiment")
async def sentiment(req: SentimentRequest):
    if req.text.strip() not in industries:
        return {"error": "Invalid industry. Please provide a valid industry name."}
    if not MySettings.NEWS_API_KEY:
        return {"error": "NEWS_API_KEY environment variable not set."}

    q = industries[req.text.strip()]
    to_date = datetime.utcnow().date()
    from_date = to_date - timedelta(days=7)

    articles, error = fetch_news_articles(q, from_date, to_date)
    if error:
        return error

    titles = extract_titles(articles)
    text = "\n".join(titles)

    sentiment_data, error = analyze_sentiment(text)
    if error:
        return error

    return {"sentiments": sentiment_data}

@sentiment_router.post("/market/sentiment")
async def market_sentiment(req: SentimentRequest):
    if not MySettings.NEWS_API_KEY:
        return {"error": "NEWS_API_KEY environment variable not set."}

    q = req.text.strip()
    to_date = datetime.utcnow().date()
    from_date = to_date - timedelta(days=7)

    articles, error = fetch_news_articles(q, from_date, to_date, page_size=5, search_in_title=True)
    if error:
        return error

    urls = [article["url"] for article in articles] # type: ignore
    url_title_pair = extract_urls_titles(articles)
    sentiment_text = "\n".join(extract_titles(articles))

    text_corpus = scrape_article_with_newspaper(urls)

    gemini_response = generate_gemini_report(text_corpus)
    if gemini_response and gemini_response.sentiment:
        sentiment_text = gemini_response.sentiment

    sentiment_data, error = analyze_sentiment(sentiment_text)
    if error:
        return error

    report = gemini_response.report if gemini_response and gemini_response.report else "No report generated."
    return {
        "report": report,
        "sentiment": sentiment_data,
        "sources": url_title_pair,
    }