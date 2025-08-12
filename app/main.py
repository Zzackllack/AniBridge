from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from pathlib import Path
from app.downloader import download_episode, Provider, Language

app = FastAPI(title="AniBridge-Minimal")

class DownloadRequest(BaseModel):
    link: str | None = Field(default=None, description="Direkter Episodenlink von aniworld.to")
    slug: str | None = Field(default=None, description="z.B. demon-slayer-kimetsu-no-yaiba")
    season: int | None = None
    episode: int | None = None
    provider: Provider = "VOE"
    language: Language = "German Dub"
    title_hint: str | None = None

class DownloadResponse(BaseModel):
    path: str

@app.post("/downloader/download", response_model=DownloadResponse)
def api_download(req: DownloadRequest):
    try:
        dest = download_episode(
            link=req.link,
            slug=req.slug,
            season=req.season,
            episode=req.episode,
            provider=req.provider,
            language=req.language,
            dest_dir=Path("/data/downloads/anime"),
            title_hint=req.title_hint,
        )
        return DownloadResponse(path=str(dest))
    except PermissionError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Download-Verzeichnis nicht beschreibbar. Setze ANIBRIDGE_DOWNLOAD_DIR oder passe die Rechte an. Systemfehler: {e}"
    )
    except OSError as e:
        raise HTTPException(status_code=400, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
