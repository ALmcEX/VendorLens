from __future__ import annotations

import os

import uvicorn


def run() -> None:
    uvicorn.run(
        "vendorlens_api.runtime:create_runtime_app",
        factory=True,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
    )


if __name__ == "__main__":
    run()
