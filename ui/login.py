"""Sign-in. Demo: pick an account. Production: University of Rochester sign-in (NetID)."""
import streamlit as st

from eir.access import Role
from ui import state

ROLE_LABEL = {Role.FOUNDER: "Founder", Role.STAFF: "AIN staff"}


def render() -> None:
    st.markdown("<div class='eyebrow'>AIN Center · Virtual Entrepreneur in Residence</div>", unsafe_allow_html=True)
    st.title("Sign in")
    left, right = st.columns([1.1, 1], gap="large")

    with left, st.container(border=True):
        accounts = state.accounts()
        chosen = st.selectbox("Account (demo)", [a.id for a in accounts],
                              format_func=lambda i: next(f"{a.name} · {ROLE_LABEL[a.role]}" for a in accounts if a.id == i))
        st.button("Sign in", type="primary", use_container_width=True, on_click=state.sign_in, args=(chosen,))
        st.caption("Prototype only: no password. The real version uses University of Rochester sign-in.")

    with right:
        st.markdown("**What each account can see**")
        st.markdown(
            "- **Founders** see only their own venture. Other teams' ventures are never listed.\n"
            "- **AIN staff** see a directory of ventures and the Human EIR briefs a team chose to share. "
            "Never conversations, canvases or venture memory.\n"
            "- **IP-sensitive ventures** (e.g. lab IP with UR Ventures): the EIR does not collect technical details.")
