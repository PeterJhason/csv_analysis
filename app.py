import streamlit as st
import pandas as pd
import json
from io import BytesIO
from dateutil import parser  # Corrected import
import os

st.set_page_config(layout="wide")
st.title("🖱️🧠 Mouse & Keyboard Activity Analyzer")

uploaded_file = st.file_uploader("Upload your CSV file (with headers: happenedAt, type, subType, eventData)", type="csv")

def parse_csv(file):
    df = pd.read_csv(file)
    events = []

    for _, row in df.iterrows():
        payload_str = str(row.get("eventData", "")).strip()
        if not payload_str.startswith("{"):
            continue

        try:
            payload = json.loads(payload_str)
            timestamp = payload.get("happenedAt")
            if isinstance(timestamp, str):
                # ✅ Use dateutil parser to properly handle ISO timestamps with 'Z'
                timestamp = parser.parse(timestamp).timestamp()
            x, y = payload.get("location", [None, None])
            button = payload.get("buttonNumber", None)
            subtype = str(row.get("subType", "")).strip().lower()
            delta = payload.get("scrollWheelDelta", {})
            key = payload.get("characters", "")

            events.append({
                "Time": timestamp,
                "X": x,
                "Y": y,
                "Type": subtype,
                "Button": button,
                "DeltaX": delta.get("x", 0),
                "DeltaY": delta.get("y", 0),
                "Key": key
            })
        except Exception:
            continue

    return pd.DataFrame(events)

def get_button_name(button):
    if button == 0:
        return "left"
    elif button == 1:
        return "right"
    elif button == 2:
        return "middle"
    return "unknown"

def analyze_mouse_keyboard_data(df):
    df = df.sort_values("Time").reset_index(drop=True)
    summary = []
    i = 0
    base_time = df["Time"].min()

    while i < len(df):
        row = df.iloc[i]
        t = row["Time"]
        x, y = row["X"], row["Y"]
        typ = row["Type"]

        # Mouse Movement
        if typ == "mouse_move":
            j = i + 1
            while j < len(df) and df.loc[j, "Type"] == "mouse_move":
                j += 1
            end_row = df.iloc[j - 1]
            summary.append({
                "Time From": row["Time"],
                "Time To": end_row["Time"],
                "Coord From": f"{x},{y}",
                "Coord To": f"{end_row['X']},{end_row['Y']}",
                "Activity": "Mouse Move"
            })
            i = j

        # Mouse Clicks
        elif typ == "mouse_down":
            button = get_button_name(row["Button"])
            j = i + 1
            while j < len(df):
                if df.loc[j, "Type"] == "mouse_up" and df.loc[j, "Button"] == row["Button"]:
                    end_row = df.loc[j]
                    summary.append({
                        "Time From": row["Time"],
                        "Time To": end_row["Time"],
                        "Coord From": f"{x},{y}",
                        "Coord To": f"{end_row['X']},{end_row['Y']}",
                        "Activity": f"Mouse Click {button}"
                    })
                    i = j + 1
                    break
                j += 1
            else:
                i += 1

        # Scroll Events
        elif typ == "scroll_wheel":
            direction = "Scroll Down" if row["DeltaY"] > 0 else "Scroll Up"
            j = i + 1
            while j < len(df) and df.loc[j, "Type"] == "scroll_wheel":
                if ((df.loc[j, "DeltaY"] > 0 and row["DeltaY"] > 0) or (df.loc[j, "DeltaY"] < 0 and row["DeltaY"] < 0)) and \
                   (df.loc[j, "Time"] - row["Time"] < 1.0):
                    j += 1
                else:
                    break
            end_row = df.iloc[j - 1]
            summary.append({
                "Time From": row["Time"],
                "Time To": end_row["Time"],
                "Coord From": f"{x},{y}",
                "Coord To": f"{end_row['X']},{end_row['Y']}",
                "Activity": direction
            })
            i = j

        # Typing (Key Down + Key Up)
        elif typ == "key_down":
            key_char = row["Key"] or "Unknown"
            j = i + 1
            while j < len(df):
                if df.loc[j, "Type"] == "key_up" and df.loc[j, "Key"] == key_char:
                    end_row = df.loc[j]
                    summary.append({
                        "Time From": row["Time"],
                        "Time To": end_row["Time"],
                        "Coord From": "N/A",
                        "Coord To": "N/A",
                        "Activity": f"Key Presses: {key_char}"
                    })
                    i = j + 1
                    break
                j += 1
            else:
                i += 1

        else:
            i += 1

    # Build final dataframe
    result = pd.DataFrame(summary)

    # ✅ Sort chronologically based on raw float values
    result["Time From"] = result["Time From"].astype(float)
    result["Time To"] = result["Time To"].astype(float)

    base_time = result["Time From"].min()
    result["Time From"] = result["Time From"] - base_time
    result["Time To"] = result["Time To"] - base_time

    result = result.sort_values(by="Time From").reset_index(drop=True)

    # Format time fields for readability
    result["Time From"] = result["Time From"].apply(lambda t: f"[{round(t, 3)}]")
    result["Time To"] = result["Time To"].apply(lambda t: f"[{round(t, 3)}]")

    return result

# Main app logic
if uploaded_file is not None:
    base_name = os.path.splitext(uploaded_file.name)[0]
    output_file = f"{base_name}_analyzed.xlsx"

    parsed_df = parse_csv(uploaded_file)

    if parsed_df.empty:
        st.error("Parsed data is empty or invalid.")
        st.stop()

    analyzed_df = analyze_mouse_keyboard_data(parsed_df)

    st.subheader("✅ Mouse & Keyboard Activity Log")
    st.dataframe(analyzed_df)

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        analyzed_df.to_excel(writer, index=False, sheet_name="Activity Log")
    output.seek(0)

    st.download_button(
        label="📥 Download Excel",
        data=output,
        file_name=output_file,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
