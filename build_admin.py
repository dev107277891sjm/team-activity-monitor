import subprocess
import sys
from datetime import datetime

def build():
    date_str = datetime.now().strftime("%Y%m%d")
    name = f"tam_admin_{date_str}"

    hidden_imports = [
        # uvicorn internals
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.loops.asyncio",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.http.httptools_impl",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.protocols.websockets.wsproto_impl",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "uvicorn.lifespan.off",
        # fastapi / starlette internals
        "fastapi",
        "fastapi.staticfiles",
        "starlette.responses",
        "starlette.routing",
        "starlette.middleware",
        "starlette.middleware.cors",
        "starlette.staticfiles",
        "anyio._backends._asyncio",
        "multipart",
        "multipart.multipart",
        # database module (sibling import from app.py)
        "database",
        # bcrypt
        "bcrypt",
        "bcrypt._bcrypt",
        # email
        "email.mime.text",
        "email.mime.multipart",
        "email.mime.base",
        # sqlite
        "sqlite3",
        # json
        "json",
    ]

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--console",
        f"--name={name}",
        "--add-data", "server/static;server/static",
        "--add-data", "server/database.py;.",
    ]

    for imp in hidden_imports:
        cmd.extend(["--hidden-import", imp])

    cmd.append("server/app.py")

    print(f"Building {name}.exe ...")
    subprocess.run(cmd, check=True)
    print(f"\nDone! Output: dist/{name}.exe")

if __name__ == "__main__":
    build()
