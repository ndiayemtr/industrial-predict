from fastapi import FastAPI;

app = FastAPI(
    title="Industrial Predict AI API",
    description="API de maintenance prédictive industrielle",
    version="0.1.0",
)

@app.get("/health")
def health_check():
    return {"status": "healthy"}