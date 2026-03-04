from __future__ import annotations
import streamlit as st

def select_or_other(*, label: str, options: list[str], value: str | None, key: str,
                    none_label: str="(none)", other_label: str="(other...)") -> str | None:
    opts = sorted(set([o for o in options if o]), key=lambda x: x.lower())
    base = [none_label] + opts + [other_label]

    if value and value in opts:
        idx = base.index(value)
    elif value:
        idx = base.index(other_label)
    else:
        idx = 0

    chosen = st.selectbox(label, base, index=idx, key=f"{key}__sel")
    if chosen == none_label:
        return None
    if chosen == other_label:
        typed = st.text_input(f"{label} (other)", value=value or "", key=f"{key}__other")
        typed = (typed or "").strip()
        return typed or None
    return chosen