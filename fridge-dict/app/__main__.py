"""python -m app  → PORT(기본 8080)에서 uvicorn 실행. Dockerfile의 CMD."""
import uvicorn

from .config import PORT

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=PORT, proxy_headers=True, forwarded_allow_ips="*")
