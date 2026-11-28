"""Read-only GitHub access for Super Agent.

With a token set, Super Agent can read a pull request, its diff and checks, files and code
search results itself. It is given only functions that read: nothing here can push, comment,
open or change anything on GitHub. Without a token it gets nothing and the platform starts
as before.
"""

from os import getenv
from typing import Any

from agno.tools.github import GithubTools

# Every function here reads. A function that writes must never be added to this list.
READ_FUNCTIONS = (
    "get_pull_request",
    "get_pull_request_changes",
    "get_pull_request_checks",
    "get_pull_request_comments",
    "get_pull_requests",
    "get_file_content",
    "get_directory_content",
    "list_branches",
    "search_code",
)

INSTRUCTIONS = """\
GitHub: you can read GitHub yourself with the get_pull_request, get_pull_request_changes,
get_pull_request_checks, get_file_content and search_code tools. You cannot write to it.
- Asked about a pull request, read it before you answer: get_pull_request for its state and head
  commit, get_pull_request_changes for the diff, get_pull_request_checks for CI. Answer from what
  you read and say which commit it was.
- When an agent, a Task or a workflow tells you something about a pull request or a file, read the
  pull request or the file before you repeat it as true. If what you read disagrees, say so.
- For a large pull request, list the files first (get_pull_request_changes with
  include_patches=false), then read the files that matter one at a time with path. Say which files
  you did not read.
- "Safe to merge" is your judgment from the diff and the checks. Say what you checked and what
  you could not: you do not run the code.
"""


def github_token() -> str | None:
    """The token Super Agent reads GitHub with: the read-only one when set, else the engineers' token."""
    return getenv("GITHUB_READ_TOKEN") or getenv("GH_TOKEN") or None


def github_read_tools() -> list[Any]:
    """The read-only GitHub functions, or nothing when no token is set."""
    token = github_token()
    return [GithubTools(access_token=token, include_tools=list(READ_FUNCTIONS))] if token else []


def github_instructions() -> str | None:
    """What Super Agent is told about reading GitHub, or nothing when it has no access."""
    return INSTRUCTIONS if github_token() else None
