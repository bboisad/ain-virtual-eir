"""Screenshots of the main screens in the system Edge, to check the layout by eye. Uses fictional demo data only.

1. Start the app with the scripted Virtual EIR and in-memory data (no API calls, nothing saved), from virtual_eir/:
   $env:EIR_STORAGE="memory"; streamlit run app.py --server.headless true --server.port 8766 --secrets.files <empty.toml>
2. Then:  python scripts/shoot_ui.py <output dir> [width] [height] [--overview | --drawer | --files | --practice]
   (--overview: the Overview homepage with its focus card, an evidence label, the key questions and snapshot
   dialogs, a file added and discussed in the chat, a new project's start page and its page after the first message;
   --drawer: the consultant rail and drawer; --files: a real upload in the Virtual EIR chat, then the files on the
   Overview; --practice: the Practice page, a pitch to the judge and its feedback, the setup dialog and a hint)
"""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

URL = "http://localhost:8766/"
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
OUT = Path(ARGS[0] if ARGS else ".")
WIDTH = int(ARGS[1]) if len(ARGS) > 1 else 1366
HEIGHT = int(ARGS[2]) if len(ARGS) > 2 else 900
CHAT = "Message your Launch Virtual EIR"


def shoot(page: Page, name: str, full: bool = True) -> None:
    page.wait_for_timeout(900)
    path = OUT / f"{WIDTH}_{name}.png"
    page.screenshot(path=str(path), full_page=full)
    print("saved", path)


def button(page: Page, name: str) -> None:
    page.get_by_role("button", name=name, exact=False).first.click()
    page.wait_for_timeout(1200)


def open_campus(page: Page) -> None:
    """Sign in as the first demo account (Alice) and open Campus Loop: it lands on the Virtual EIR chat."""
    page.goto(URL)
    page.get_by_role("button", name="Sign in").wait_for(timeout=30000)
    button(page, "Sign in")
    page.get_by_role("button", name="Open", exact=True).first.wait_for(timeout=15000)
    page.wait_for_timeout(800)
    page.get_by_role("button", name="Open", exact=True).first.click()
    page.get_by_placeholder(CHAT).wait_for(timeout=15000)


def drawer(page: Page) -> None:
    """The consultant rail and drawer: bring in the pricing consultant, talk, preview the summary, collapse."""
    open_campus(page)
    shoot(page, "10_rail", full=False)
    page.get_by_role("button", name="P", exact=True).click()
    page.get_by_text("Brief from your Virtual EIR").wait_for(timeout=30000)
    shoot(page, "11_drawer_open", full=False)
    for _ in range(3):
        prepared = page.locator("[class*='st-key-csuggest_'] button").first
        if not prepared.is_visible():
            page.locator(".st-key-consult_drawer").get_by_text("Prepared messages (demo)").click()
            page.wait_for_timeout(500)
        prepared.click()
        page.wait_for_timeout(2500)
    shoot(page, "12_drawer_proposal", full=False)
    button(page, "Collapse")
    page.get_by_placeholder(CHAT).wait_for(timeout=15000)
    shoot(page, "13_collapsed", full=False)
    page.get_by_role("button", name="P", exact=True).click()
    page.get_by_role("button", name="Review the summary").click()
    page.get_by_text("Summary for your Virtual EIR").wait_for(timeout=30000)
    shoot(page, "14_summary_preview", full=False)
    note = page.get_by_placeholder("e.g. I still want to try $3 first")
    note.fill("I still want to try $3 first")
    note.press("Tab")
    page.wait_for_timeout(1000)
    page.get_by_role("button", name="Send to my Virtual EIR").click()
    page.get_by_text("Record updates", exact=False).first.wait_for(timeout=30000)
    shoot(page, "15_after_send", full=False)
    page.get_by_role("button", name="P", exact=True).click()
    page.get_by_text("Sent to your Virtual EIR", exact=False).wait_for(timeout=15000)
    shoot(page, "16_done_view", full=False)


SURVEY = ("# Pricing survey (fictional demo)\nWe asked 40 students at the dining hall.\n"
          "- 28 of 40 said they would pay $3 to sell a mini-fridge.\n- 9 of 40 had already sold furniture online.\n")


def _survey() -> Path:
    path = OUT / "Pricing survey.md"
    path.write_text(SURVEY, encoding="utf-8")
    return path


def _to_overview(page: Page, wait: str = "Current focus") -> None:
    page.locator(".st-key-topbar").get_by_text("Overview", exact=True).click()
    page.get_by_text(wait, exact=False).first.wait_for(timeout=15000)


def _dialog(page: Page, button_name: str, shot: str, exact: bool = False) -> None:
    """Open a dialog from a button on the page, take a shot, close it with Escape."""
    page.get_by_role("button", name=button_name, exact=exact).first.click()
    page.get_by_role("dialog").wait_for(timeout=15000)
    page.wait_for_timeout(600)
    shoot(page, shot, full=False)
    page.keyboard.press("Escape")
    page.get_by_role("dialog").wait_for(state="detached", timeout=15000)
    page.wait_for_timeout(600)


def project_files(page: Page) -> None:
    """A real upload through the chat's attach button, then the files on the Overview."""
    survey = _survey()
    open_campus(page)
    box = page.get_by_placeholder(CHAT)
    page.locator("[data-testid='stChatInput'] input[type='file']").set_input_files(str(survey))
    page.wait_for_timeout(1500)
    box.fill("Our survey results")
    box.press("Enter")
    page.get_by_text("Pricing survey.md · version 1").first.wait_for(timeout=30000)
    page.get_by_text("Record updates", exact=False).last.wait_for(timeout=30000)
    shoot(page, "20_upload_reply", full=False)
    _to_overview(page)
    page.get_by_role("button", name="Add a file").first.scroll_into_view_if_needed()
    shoot(page, "21_project_files", full=False)
    survey.unlink()


def overview_flow(page: Page) -> None:
    """The Overview (v0.19): Campus Loop's homepage, an evidence label, the key questions, a snapshot line, adding a
    file and discussing it in the chat; then a new project's start page and its page after the first message."""
    survey = _survey()
    open_campus(page)
    _to_overview(page)
    shoot(page, "50_overview_top", full=False)
    page.mouse.wheel(0, 700)  # the page scrolls inside Streamlit's container: no full-page shot
    shoot(page, "51_overview_lower", full=False)
    page.mouse.wheel(0, -20000)
    page.get_by_role("button", name="Customer statements · Level 3").first.click()
    page.get_by_text("Where it comes from").first.wait_for(timeout=15000)
    shoot(page, "52_evidence_popover", full=False)
    page.keyboard.press("Escape")
    page.wait_for_timeout(600)
    _dialog(page, "See all key questions", "53_key_questions")
    _dialog(page, "Business model", "54_snapshot_dialog", exact=True)
    page.get_by_role("button", name="Add a file").first.click()
    page.get_by_role("dialog").wait_for(timeout=15000)
    page.get_by_role("dialog").locator("input[type='file']").set_input_files(str(survey))
    page.get_by_text("Saved Pricing survey.md", exact=False).wait_for(timeout=30000)
    page.wait_for_timeout(600)
    shoot(page, "55_saved_offer", full=False)
    page.get_by_placeholder("e.g. Is the pricing slide convincing?").fill("Is the $3 price convincing?")
    page.get_by_placeholder("e.g. Is the pricing slide convincing?").press("Tab")
    page.wait_for_timeout(800)
    page.get_by_role("button", name="Read and discuss it").click()
    page.get_by_placeholder(CHAT).wait_for(timeout=30000)
    page.get_by_text("Pricing survey.md · version 1").first.wait_for(timeout=30000)
    page.wait_for_timeout(1500)
    shoot(page, "56_discussed_in_chat", full=False)
    _to_overview(page)
    _dialog(page, "Pricing survey.md", "57_file_dialog")
    survey.unlink()
    page.locator("[class*='st-key-menu_'] button").first.click()  # a new project, from My projects
    page.get_by_role("button", name="My projects").click()
    page.get_by_label("Project name").wait_for(timeout=15000)
    page.get_by_label("Project name").fill("Lab Share")
    page.get_by_label("One-line description").fill("Shared lab equipment booking for grad students")
    button(page, "Next: choose your Virtual EIR")
    page.get_by_role("button", name="Start with Launch").click()
    page.get_by_placeholder(CHAT).wait_for(timeout=15000)
    _to_overview(page, "Your project, just started")
    shoot(page, "58_new_project_start", full=False)
    page.get_by_role("button", name="Start the conversation").click()
    box = page.get_by_placeholder(CHAT)
    box.wait_for(timeout=15000)
    box.fill("We want to help grad students share idle lab equipment. Three labs said they would try it.")
    box.press("Enter")
    page.wait_for_timeout(3500)
    _to_overview(page)
    shoot(page, "59_new_project_after_first_message", full=False)


def practice_flow(page: Page) -> None:
    """The Practice page: home; a pitch to the judge with the prepared lines and its feedback; the setup dialog for a
    customer interview, one question and a hint."""
    open_campus(page)
    page.get_by_text("Practice", exact=True).first.click()
    page.get_by_text("Recommended now").wait_for(timeout=15000)
    shoot(page, "30_practice_home", full=False)
    page.locator(".st-key-practice_rec_start button").click()
    page.get_by_placeholder("Type or paste your pitch…").wait_for(timeout=15000)
    shoot(page, "31_session_start", full=False)
    for i in range(5):
        prepared = page.locator("[class*='st-key-psuggest_'] button").first
        if not prepared.is_visible():
            page.get_by_text("Prepared messages (demo)").click()
            page.wait_for_timeout(500)
        prepared.click()
        page.wait_for_timeout(2200)
        if i == 0:
            shoot(page, "32_after_pitch", full=False)
    page.get_by_text("has wrapped up", exact=False).wait_for(timeout=15000)
    shoot(page, "33_wrapped_up", full=False)
    button(page, "Get my feedback")
    page.get_by_text("Fix these first").wait_for(timeout=15000)
    shoot(page, "34_feedback", full=False)
    page.mouse.wheel(0, 650)
    shoot(page, "35_feedback_lower", full=False)
    page.locator("[class*='st-key-psend_menu_'] button").first.click()
    note = page.get_by_placeholder("e.g. The money question froze me")
    note.wait_for(timeout=15000)
    note.fill("The money question froze me")
    note.press("Tab")
    page.wait_for_timeout(600)
    shoot(page, "36_send_popover", full=False)
    page.get_by_role("button", name="Send", exact=True).click()
    page.get_by_role("button", name="See your Virtual EIR's reply").wait_for(timeout=30000)
    button(page, "See your Virtual EIR's reply")
    page.get_by_role("button", name="Practice feedback you sent", exact=False).wait_for(timeout=15000)
    page.get_by_role("button", name="Practice feedback you sent", exact=False).scroll_into_view_if_needed()
    shoot(page, "37_mentor_reply", full=False)
    page.get_by_text("Prepared messages (demo)").click()
    page.wait_for_timeout(600)
    page.get_by_role("button", name="pitching at Foundry Friday", exact=False).first.click()
    suggestion = page.get_by_role("button", name="Practise with the competition judge", exact=False)
    suggestion.wait_for(timeout=15000)
    suggestion.scroll_into_view_if_needed()
    shoot(page, "38_mentor_suggests_practice", full=False)
    suggestion.click()
    page.get_by_role("dialog").wait_for(timeout=15000)
    shoot(page, "39_setup_from_mentor", full=False)
    page.keyboard.press("Escape")
    page.wait_for_timeout(1200)
    page.mouse.wheel(0, 700)
    shoot(page, "40_practice_history", full=False)
    page.locator(".st-key-practise_customer button").click()
    page.get_by_role("dialog").wait_for(timeout=15000)
    shoot(page, "41_setup_customer", full=False)
    page.get_by_role("button", name="Start practice").click()
    box = page.get_by_placeholder("Ask Maya a question…")
    box.wait_for(timeout=15000)
    box.fill("Would you pay $3 to have someone sell your stuff for you?")
    box.press("Enter")
    page.wait_for_timeout(2500)
    button(page, "Stuck? Get a hint")
    page.locator(".hint-note").first.wait_for(timeout=15000)
    shoot(page, "42_customer_hint", full=False)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        for flag, flow in (("--overview", overview_flow), ("--drawer", drawer), ("--files", project_files),
                           ("--practice", practice_flow)):
            if flag in sys.argv:
                flow(browser.new_page(viewport={"width": WIDTH, "height": HEIGHT}))
                browser.close()
                return
        page = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT})
        page.goto(URL)
        page.get_by_role("button", name="Sign in").wait_for(timeout=30000)
        button(page, "Sign in")  # the first demo account: Alice
        page.get_by_label("Project name").wait_for(timeout=15000)
        shoot(page, "1_lobby", full=False)
        page.get_by_label("Project name").fill("Lab Share")
        button(page, "Next: choose your Virtual EIR")
        page.get_by_text("We recommend", exact=False).wait_for(timeout=15000)
        page.get_by_text("We recommend", exact=False).scroll_into_view_if_needed()
        shoot(page, "2_choose_mentor", full=False)
        button(page, "Back")
        button(page, "Open")
        page.get_by_placeholder(CHAT).wait_for(timeout=15000)
        shoot(page, "3_mentor", full=False)
        page.get_by_text("Prepared messages (demo)").click()
        page.wait_for_timeout(600)
        page.get_by_role("button", name="I'm sure they'll pay", exact=False).first.click()
        page.get_by_text("Record updates", exact=False).first.wait_for(timeout=15000)
        page.get_by_text("Record updates", exact=False).first.click()
        shoot(page, "4_mentor_after_reply", full=False)
        _to_overview(page)
        shoot(page, "5_overview", full=False)
        page.mouse.wheel(0, 700)
        shoot(page, "6_overview_lower", full=False)
        page.get_by_text("Action Plan", exact=True).first.click()
        page.get_by_text("Experiments", exact=True).wait_for(timeout=15000)
        shoot(page, "7_action_plan", full=False)
        page.locator("[class*='st-key-menu_'] button").first.click()
        page.get_by_role("button", name="Switch Virtual EIR").wait_for(timeout=15000)
        shoot(page, "8_menu", full=False)
        page.get_by_role("button", name="Switch Virtual EIR").click()
        page.get_by_role("dialog").wait_for(timeout=15000)
        shoot(page, "9_switch_dialog", full=False)
        browser.close()


if __name__ == "__main__":
    main()
