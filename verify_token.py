#!/usr/bin/env python3
import subprocess
import os
import sys
import json

# Determine the directory where the script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE = os.path.join(SCRIPT_DIR, "github_token.txt")
REPO_OWNER = "soberlevi"
REPO_NAME = "claude-code"

def main():
    token = None
    if os.path.isfile(TOKEN_FILE):
        with open(TOKEN_FILE, 'r') as f:
            token = f.read().strip()
    elif os.environ.get("GITHUB_TOKEN"):
        token = os.environ.get("GITHUB_TOKEN")

    if not token:
        print(f"Error: No token found in {TOKEN_FILE} or GITHUB_TOKEN env var.")
        sys.exit(1)

    print(f"Token found (length: {len(token)})")
    if token.startswith("github_pat_"):
        print("Type: Fine-grained Personal Access Token")
    elif token.startswith("ghp_"):
        print("Type: Classic Personal Access Token")
    else:
        print("Type: Unknown format")

    # Check User
    print("\n--- Checking User Identity ---")
    try:
        cmd = [
            "curl", "-s", "-I", "-H", f"Authorization: token {token}",
            "https://api.github.com/user"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        print("Headers check:")
        for line in result.stdout.splitlines():
            if "x-oauth-scopes" in line.lower() or "x-accepted-oauth-scopes" in line.lower():
                print(line)

        cmd = [
            "curl", "-s", "-H", f"Authorization: token {token}",
            "https://api.github.com/user"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(result.stdout)

        if "login" in data:
            print(f"Authenticated as: {data['login']}")
        else:
            print("Authentication Failed!")
            print(f"Response: {result.stdout}")
            sys.exit(1)

    except Exception as e:
        print(f"Error checking user: {e}")

    # Check Repo Permissions
    print(f"\n--- Checking Permissions for {REPO_OWNER}/{REPO_NAME} ---")
    try:
        cmd = [
            "curl", "-s", "-H", f"Authorization: token {token}",
            f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(result.stdout)

        if "permissions" in data:
            perms = data["permissions"]
            print(f"API Reported User Permissions (may not match Token): {json.dumps(perms, indent=2)}")
        elif "message" in data:
             print(f"Error accessing repo: {data['message']}")
    except Exception as e:
         print(f"Error checking repo: {e}")

if __name__ == "__main__":
    main()
