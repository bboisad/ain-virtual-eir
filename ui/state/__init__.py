"""Session state for the Streamlit app. All `st.session_state` access lives in this package,
so pages never touch raw keys (widget keys aside).

- core.py  sign-in, open venture, current page, menu dialog, consultant drawer, practice session and setup,
           the Overview's upload box, the file just saved there and the file to discuss in the chat, PageContext
"""
from .core import (HOME, PRACTICE, AppState, PageContext, account, accounts, app_state, clear_saved_file,
                   cloud_storage, require_demo_access, render_unsaved, setting,
                   close_dialog, close_drawer, close_practice_setup, close_rehearsal, coach, context, dialog, drawer,
                   file_saved, flash, go_to, leave_venture, nav_key, navigated, next_upload_round, open_dialog,
                   open_drawer, open_practice_setup, open_rehearsal, open_venture, pop_discussion, pop_flash,
                   pop_invite, practice_setup, rehearsal, repo, request_discussion, request_invite, reset, saved_file,
                   sign_in, sign_out, upload_round)

__all__ = ["HOME", "PRACTICE", "AppState", "PageContext", "account", "accounts", "app_state", "clear_saved_file",
           "cloud_storage", "require_demo_access", "render_unsaved", "setting",
           "close_dialog", "close_drawer", "close_practice_setup", "close_rehearsal", "coach", "context", "dialog",
           "drawer", "file_saved", "flash", "go_to", "leave_venture", "nav_key", "navigated", "next_upload_round",
           "open_dialog", "open_drawer", "open_practice_setup", "open_rehearsal", "open_venture", "pop_discussion",
           "pop_flash", "pop_invite", "practice_setup", "rehearsal", "repo", "request_discussion", "request_invite",
           "reset", "saved_file", "sign_in", "sign_out", "upload_round"]
