#!/usr/bin/env python3
import subprocess
import os
import sys
import datetime
import shutil
import argparse

# Determine the directory where the script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Configuration
REPO_OWNER = "soberlevi"
REPO_NAME = "claude-code"
FULL_REPO = f"{REPO_OWNER}/{REPO_NAME}"
BRANCH = "main"
TOKEN_FILE = os.path.join(SCRIPT_DIR, "github_token.txt")

def run_command(command, check=True, capture_output=True, input_text=None):
    """Run a shell command."""
    try:
        result = subprocess.run(
            command,
            check=check,
            shell=True,
            text=True,
            capture_output=capture_output,
            input=input_text
        )
        return result
    except subprocess.CalledProcessError as e:
        if check:
            print(f"Error running command: {command}")
            print(f"Stderr: {e.stderr}")
            sys.exit(1)
        return e

def check_command_exists(cmd):
    """Check if a command is available."""
    if not shutil.which(cmd):
        print(f"Error: {cmd} is not installed.")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Upload meeting content to GitHub.")
    parser.add_argument("--content", help="Meeting summary content to save to a file before uploading.")
    args = parser.parse_args()

    created_file = None
    # Handle content argument if provided
    if args.content:
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"meeting_summary_{timestamp}.md"
        try:
            with open(filename, "w") as f:
                f.write(args.content)
            print(f"Created meeting summary file: {filename}")
            created_file = filename
        except Exception as e:
            print(f"Error writing content to file: {e}")
            sys.exit(1)

    # Ensure gh and git are installed
    check_command_exists("gh")
    check_command_exists("git")

    # Check authentication
    print("Checking GitHub authentication status...")
    auth_check = run_command("gh auth status", check=False)

    token = None

    if auth_check.returncode != 0:
        print("Not logged in to GitHub CLI.")

        # Try to login with token file
        if os.path.isfile(TOKEN_FILE):
            print(f"Found {TOKEN_FILE}, attempting to login...")
            try:
                with open(TOKEN_FILE, 'r') as f:
                    token = f.read().strip()

                login_result = run_command("gh auth login --with-token", input_text=token, check=False)
                if login_result.returncode == 0:
                    print("Successfully logged in with token.")
                else:
                    print(f"Failed to login with token from {TOKEN_FILE}.")
                    sys.exit(1)
            except Exception as e:
                print(f"Error reading token file: {e}")
                sys.exit(1)

        # Try to login with GITHUB_TOKEN env var
        elif os.environ.get("GITHUB_TOKEN"):
            print("Found GITHUB_TOKEN environment variable, attempting to login...")
            token = os.environ.get("GITHUB_TOKEN")
            login_result = run_command("gh auth login --with-token", input_text=token, check=False)
            if login_result.returncode == 0:
                print("Successfully logged in with token.")
            else:
                print("Failed to login with GITHUB_TOKEN.")
                sys.exit(1)
        else:
            print(f"Error: Please login using 'gh auth login' or create a '{TOKEN_FILE}' file with your Personal Access Token.")
            print("Note: GitHub no longer supports password authentication for CLI. You must use a token.")
            print("Generate one at: https://github.com/settings/tokens")
            sys.exit(1)

    # Try to retrieve token if not already read, for git operations
    if not token and os.path.isfile(TOKEN_FILE):
        try:
             with open(TOKEN_FILE, 'r') as f:
                token = f.read().strip()
        except:
            pass

    if not token and os.environ.get("GITHUB_TOKEN"):
        token = os.environ.get("GITHUB_TOKEN")

    # Construct Authenticated URL
    auth_url = None
    if token:
        # Use REPO_OWNER as username for broad compatibility
        auth_url = f"https://{REPO_OWNER}:{token}@github.com/{FULL_REPO}.git"
        print(f"Using authenticated URL with token ending in ...{token[-4:]}")
    else:
        print("Warning: Could not retrieve raw token. Git operations may prompt for credentials.")

    # Initialize git if needed
    if not os.path.isdir(".git"):
        print("Initializing git repository...")
        run_command("git init")
        run_command(f"git branch -M {BRANCH}")

    # Check if repository exists on GitHub
    print(f"Checking if repository {FULL_REPO} exists...")
    repo_check = run_command(f"gh repo view {FULL_REPO}", check=False)

    if repo_check.returncode == 0:
        print("Repository exists.")
        # Ensure remote is configured
        remote_check = run_command("git remote", check=False)
        if "origin" not in remote_check.stdout.splitlines():
            print("Adding remote origin...")
            run_command(f"git remote add origin https://github.com/{FULL_REPO}.git")
        else:
            # Update remote URL just in case
            run_command(f"git remote set-url origin https://github.com/{FULL_REPO}.git")
    else:
        print("Repository does not exist. Creating it...")
        # Create repository and push current directory
        # Defaulting to private for safety, change to --public if needed
        run_command(f"gh repo create {FULL_REPO} --private --source=. --remote=origin")

    # Disable local credential helper to force using the token in URL
    run_command("git config --local credential.helper ''", check=False)

    # Pull latest changes to avoid conflicts
    print("Pulling latest changes...")

    pull_cmd = f"git pull origin {BRANCH} --allow-unrelated-histories --no-edit --no-rebase"
    if auth_url:
        pull_cmd = f"git pull {auth_url} {BRANCH} --allow-unrelated-histories --no-edit --no-rebase"

    # We manually run subprocess to avoid printing the token in error messages
    try:
        pull_result = subprocess.run(pull_cmd, shell=True, check=False, capture_output=True, text=True)
        if pull_result.returncode != 0:
            print(f"Pull warning/error: {pull_result.stderr}")
            print(f"Pull stdout: {pull_result.stdout}")
        else:
            print("Pull completed (success or no changes).")
    except Exception as e:
        print(f"Pull failed: {e}")

    # Add files
    print("Adding files...")

    # Ensure .gitignore exists and includes the token file
    gitignore_path = ".gitignore"
    if not os.path.exists(gitignore_path) or "github_token.txt" not in open(gitignore_path).read():
        with open(gitignore_path, "a") as f:
            f.write("\ngithub_token.txt\n")

    run_command("git add .")

    # Check for changes
    diff_check = run_command("git diff-index --quiet HEAD --", check=False)
    if diff_check.returncode == 0:
        print("No changes to commit.")
        sys.exit(0)

    # Commit
    print("Committing changes...")
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    commit_msg = f"Update meeting content: {timestamp}"
    run_command(f'git commit -m "{commit_msg}"')

    # Push
    print("Pushing to GitHub...")

    push_cmd = f"git push -u origin {BRANCH}"
    if auth_url:
        push_cmd = f"git push -u {auth_url} {BRANCH}"

    try:
        subprocess.run(push_cmd, shell=True, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print(f"Error pushing to GitHub: {e.stderr}")
        sys.exit(1)

    print("Done!")

    # Print success URL
    base_url = f"https://github.com/{FULL_REPO}/blob/{BRANCH}"
    if created_file:
        print(f"Successfully uploaded meeting summary to: {base_url}/{created_file}")
    else:
        print(f"Successfully uploaded files to: {base_url}/")
        print("Check the repository for the latest files.")

if __name__ == "__main__":
    main()
