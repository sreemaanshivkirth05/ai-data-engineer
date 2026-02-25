import base64
import requests

def render_mermaid_via_api(mermaid_code: str, output_path: str):
    """
    Renders Mermaid code to an image using the free mermaid.ink API.
    """
    if not mermaid_code or not mermaid_code.strip():
        raise ValueError("Mermaid code is empty.")

    encoded = base64.b64encode(mermaid_code.encode("utf-8")).decode("utf-8")
    url = f"https://mermaid.ink/img/{encoded}"

    resp = requests.get(url, timeout=30)
    resp.raise_for_status()

    with open(output_path, "wb") as f:
        f.write(resp.content)