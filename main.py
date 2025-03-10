from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.v1.endpoints.apiary import apiary_router
from api.v1.endpoints.auth import auth_router
from api.v1.endpoints.maps import maps_router
from api.v1.endpoints.users import user_router
load_dotenv()  # Load environment variables from .env file
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

from api.v1.endpoints.meliponary import meliponary_router

app.include_router(meliponary_router, prefix='/api/v1/meliponary', tags=['meliponary'])
app.include_router(apiary_router, prefix='/api/v1/apiaries', tags=['apiaries'])
app.include_router(user_router, prefix='/api/v1/users', tags=['users'])
app.include_router(auth_router, prefix='/api/v1/auth', tags=['Authenticate'])
app.include_router(maps_router, prefix="/api/v1/maps", tags=["maps"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, log_level='info', reload=True)
