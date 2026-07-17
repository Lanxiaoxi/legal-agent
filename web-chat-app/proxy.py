"""
Simple proxy server that serves frontend and proxies API requests to backend
"""
import os
import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

# Configuration
FRONTEND_DIR = Path(__file__).parent / "frontend"
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

app = FastAPI(title="Web Chat App Proxy")

# Serve static files from frontend directory
@app.get("/")
async def serve_index():
    """Serve the main HTML file"""
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return HTMLResponse("<h1>Frontend not found</h1>", status_code=404)

@app.get("/{path:path}")
async def serve_static(path: str):
    """Serve static files from frontend directory"""
    file_path = FRONTEND_DIR / path
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    # Fallback to index.html for SPA routing
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return HTMLResponse("<h1>Not found</h1>", status_code=404)

@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
async def proxy_api(path: str, request: Request):
    """Proxy API requests to backend"""
    # Build the target URL
    target_url = f"{BACKEND_URL}/api/{path}"
    
    # Get request body
    body = await request.body()
    
    # Get headers (excluding host)
    headers = dict(request.headers)
    headers.pop("host", None)
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.request(
                method=request.method,
                url=target_url,
                content=body,
                headers=headers,
                follow_redirects=False
            )
            
            # Return the response from backend
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers)
            )
    except httpx.ConnectError:
        return Response(
            content=b'{"error": "Backend service unavailable"}',
            status_code=502,
            media_type="application/json"
        )
    except Exception as e:
        return Response(
            content=f'{{"error": "Proxy error: {str(e)}"}}'.encode(),
            status_code=500,
            media_type="application/json"
        )


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "3000"))
    uvicorn.run(app, host="0.0.0.0", port=port)