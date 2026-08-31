"""Check the Streamlit health endpoint with bounded retries."""

from __future__ import annotations

import argparse
import time
from urllib.error import URLError
from urllib.request import urlopen


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8501/_stcore/health",
    )
    parser.add_argument("--attempts", type=int, default=15)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--timeout", type=float, default=3.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.attempts < 1 or args.interval < 0 or args.timeout <= 0:
        raise SystemExit("health check arguments are invalid")

    last_error = "no response"
    for attempt in range(1, args.attempts + 1):
        try:
            with urlopen(args.url, timeout=args.timeout) as response:
                body = response.read().decode("utf-8").strip()
                if response.status == 200 and body == "ok":
                    print("streamlit health check: OK")
                    return
                last_error = f"HTTP {response.status}: {body!r}"
        except (OSError, URLError) as error:
            last_error = str(error)
        if attempt < args.attempts:
            time.sleep(args.interval)
    raise SystemExit(f"streamlit health check: FAILED\n{last_error}")


if __name__ == "__main__":
    main()
