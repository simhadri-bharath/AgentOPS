import asyncio
import os
import sys

# Ensure backend directory is in path
sys.path.append(r"c:\Users\Sai Teja\Documents\Agentops\backend")

import vertexai
from vertexai.preview import reasoning_engines
from app.services.gcp.auth import require_adc

def test_regions():
    auth = require_adc()
    project_id = "ragmanageddb-vertexai"
    
    # Common GCP regions
    regions = [
        "us-central1",
        "us-east1",
        "us-east4",
        "us-west1",
        "us-west2",
        "us-west3",
        "us-west4",
        "europe-west1",
        "europe-west2",
        "europe-west3",
        "europe-west4",
        "europe-west9",
        "asia-east1",
        "asia-northeast1",
        "asia-southeast1",
    ]
    
    print(f"Using Project: {project_id}")
    for region in regions:
        try:
            vertexai.init(project=project_id, location=region)
            engines = reasoning_engines.ReasoningEngine.list()
            engines_list = list(engines) if engines else []
            if len(engines_list) > 0:
                print(f"\n[+] Region '{region}' found {len(engines_list)} engine(s):")
                for eng in engines_list:
                    name = getattr(eng, "display_name", None) or str(eng)
                    resource_name = getattr(eng, "resource_name", None) or "N/A"
                    print(f"  - Name: {name}")
                    print(f"    Resource Name: {resource_name}")
        except Exception as e:
            # Skip if region is not supported or failed
            pass

if __name__ == "__main__":
    test_regions()
