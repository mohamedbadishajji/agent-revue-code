from mangum import Mangum
from app.main import app

# Adaptateur AWS Lambda pour FastAPI
handler = Mangum(app, lifespan="off")