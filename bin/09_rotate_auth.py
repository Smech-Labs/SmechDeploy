#!/usr/bin/env python3
import sys
import os
import json

SETTINGS_PATH = os.path.expanduser("~/.gemini/settings.json")
ENV_PATH = os.path.expanduser("~/.gemini/.env")

def main():
    if len(sys.argv) < 2:
        print("Usage: smech-rotate [personal|enterprise] [api_key_if_enterprise]")
        sys.exit(1)
        
    mode = sys.argv[1].lower()
    
    # Load settings
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r") as f:
                settings = json.load(f)
        except Exception:
            settings = {}
    else:
        settings = {}
        
    if "security" not in settings:
        settings["security"] = {}
    if "auth" not in settings["security"]:
        settings["security"]["auth"] = {}
        
    if mode in ["personal", "oauth", "google"]:
        settings["security"]["auth"]["selectedType"] = "oauth-personal"
        with open(SETTINGS_PATH, "w") as f:
            json.dump(settings, f, indent=2)
        print("✓ Successfully rotated authentication to: Personal (OAuth Login)")
        
    elif mode in ["enterprise", "api", "studio", "key"]:
        settings["security"]["auth"]["selectedType"] = "gemini-api-key"
        
        # If user supplied a new key
        if len(sys.argv) > 2:
            key = sys.argv[2]
            with open(ENV_PATH, "w") as f:
                f.write(f'GEMINI_API_KEY="{key}"\n')
            print(f"✓ Saved new Google AI Studio API key to {ENV_PATH}")
            
        with open(SETTINGS_PATH, "w") as f:
            json.dump(settings, f, indent=2)
            
        print("✓ Successfully rotated authentication to: Enterprise (Google AI Studio API Key)")
        
        # Check if key exists
        if not os.path.exists(ENV_PATH) and "GEMINI_API_KEY" not in os.environ:
            print("⚠ Warning: No GEMINI_API_KEY detected in environment or ~/.gemini/.env")
            print("  Please run: smech-rotate enterprise <YOUR_API_KEY>")
    else:
        print("Error: Unknown mode. Use 'personal' or 'enterprise'.")
        sys.exit(1)

if __name__ == "__main__":
    main()
