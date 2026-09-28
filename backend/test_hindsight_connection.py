"""Safe connectivity verification for Hindsight Cloud."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
import httpx


def main() -> None:
    # Resolve backend/.env path relative to this script
    env_path = Path(__file__).resolve().parent / ".env"
    load_dotenv(dotenv_path=env_path)

    api_key = os.getenv("HINDSIGHT_API_KEY")
    base_url = os.getenv("HINDSIGHT_BASE_URL")

    missing_vars = []
    if not api_key:
        missing_vars.append("HINDSIGHT_API_KEY")
    if not base_url:
        missing_vars.append("HINDSIGHT_BASE_URL")

    if missing_vars:
        print(
            f"Error: Missing required environment variable(s): {', '.join(missing_vars)}"
        )
        sys.exit(1)

    endpoint_url = f"{base_url.rstrip('/')}/health/ready"
    headers = {
        "Authorization": f"Bearer {api_key}",
    }

    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(endpoint_url, headers=headers)
            print(f"HTTP Status Code: {response.status_code}")

            if response.status_code == 200:
                print("Connectivity check succeeded: Hindsight Cloud is ready.")
            else:
                print("Connectivity check failed: Received non-200 response.")
                sys.exit(1)
    except httpx.TimeoutException:
        print("Connectivity check failed: Request timed out after 15 seconds.")
        sys.exit(1)
    except httpx.RequestError:
        print("Connectivity check failed: A network connection error occurred.")
        sys.exit(1)
    except Exception:
        print("Connectivity check failed: An unexpected error occurred.")
        sys.exit(1)


if __name__ == "__main__":
    main()
