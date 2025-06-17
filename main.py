from fastapi import FastAPI
from sentiment_router.router import sentiment_router

app = FastAPI()

app.include_router(sentiment_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001, reload=True)