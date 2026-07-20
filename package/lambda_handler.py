from mangum import Mangum
from app.main_lambda import app

handler = Mangum(app, lifespan="off")