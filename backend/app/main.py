from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes_alerts, routes_gee, routes_jobs

app = FastAPI(
    title="SAR Change Sentinel",
    description=(
        "Automatic detection of man-made changes in Sentinel-1 SAR imagery, "
        "suppressing natural changes (floods, water-level shifts, snow, vegetation) "
        "and emitting georeferenced GeoJSON alerts."
    ),
    version="0.1.0",
)

# Vite dev server default port. Keep in sync with frontend/vite.config.ts if
# either port ever changes.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_jobs.router)
app.include_router(routes_alerts.router)
app.include_router(routes_gee.router)


@app.get("/")
def root():
    return {"service": "sar-change-sentinel", "status": "ok"}
