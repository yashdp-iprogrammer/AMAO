import streamlit as st
import requests
import json


st.set_page_config(page_title="AMAO")


BASE_URL = "http://localhost:8000"

# SESSION STATE INIT
if "token" not in st.session_state:
    st.session_state.token = None

if "user_data" not in st.session_state:
    st.session_state.user_data = None

if "messages" not in st.session_state:
    st.session_state.messages = []

# API HELPERS
def get_headers():
    if not st.session_state.token:
        return {}
    return {
        "Authorization": f"Bearer {st.session_state.token}"
    }


def api_login(username, password):
    url = f"{BASE_URL}/login"
    res = requests.post(url, json={"username": username, "password": password})
    res.raise_for_status()
    return res.json()


def api_get_current_user():
    url = f"{BASE_URL}/get-current-user"
    res = requests.get(url, headers=get_headers())
    res.raise_for_status()
    return res.json()


def api_chat(query, files=None):
    url = f"{BASE_URL}/chat"

    data = {"query": query}
    files_payload = []

    if files:
        for f in files:
            files_payload.append(("files", (f.name, f, f.type)))

    res = requests.post(
        url,
        data=data,
        files=files_payload,
        headers=get_headers()
    )
    res.raise_for_status()
    return res.json()


def api_get_clients():
    # If you have client listing endpoint (adjust if different)
    url = f"{BASE_URL}/clients/list-clients"
    res = requests.get(url, headers=get_headers())
    clients_obj = res.json()
    return clients_obj.get("data")


def api_create_config(client_id, config):
    url = f"{BASE_URL}/configs/create-config-file/{client_id}"
    res = requests.post(url, json=config, headers=get_headers())
    res.raise_for_status()
    return res.json()


def api_read_config(client_id):
    url = f"{BASE_URL}/configs/read-config/{client_id}"
    res = requests.get(url, headers=get_headers())
    return res.json()


# LOGIN PAGE
def login_ui():
    st.title("🚀 AMAO Enterprise Login")

    with st.container(border=True):
        u = st.text_input("Username/Email")
        p = st.text_input("Password", type="password")

        if st.button("Log In", use_container_width=True):
            try:
                data = api_login(u, p)

                st.session_state.token = data["access_token"]
                st.session_state.user_data = api_get_current_user()

                st.session_state.logged_in = True
                st.rerun()

            except Exception as e:
                st.error(f"Invalid credentials: {str(e)}")


# ASSISTANT UI
def assistant_ui(user):
    st.title("🤖 Intelligent Assistant")

    # ---- FILE UPLOAD SECTION ----
    with st.expander("📥 Upload & Index Knowledge"):
        uploaded_files = st.file_uploader(
            "Upload Documents",
            accept_multiple_files=True
        )

        if st.button("Build Index", use_container_width=True) and uploaded_files:
            with st.spinner("Processing..."):

                try:
                    # send files directly to chat endpoint (backend handles RAG)
                    api_chat("indexing_request", uploaded_files)

                    st.success("Indexed successfully!")
                    st.rerun()

                except Exception as e:
                    st.error(str(e))

    # ---- CHAT HISTORY ----
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # ---- INPUT ----
    if prompt := st.chat_input("Ask me anything..."):
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.chat_message("user"):
            st.markdown(prompt)

        with st.spinner("Thinking..."):
            try:
                result = api_chat(prompt)

                response = result.get("final_response", "No response")

                st.session_state.messages.append(
                    {"role": "assistant", "content": response}
                )

                with st.chat_message("assistant"):
                    st.markdown(response)

            except Exception as e:
                st.error(str(e))


# SUPER ADMIN UI
def superadmin_ui():
    st.title("🛠️ Super Admin Dashboard")

    tab1, tab2 = st.tabs(["🏢 Clients", "⚙️ Configs"])

    # ---------------- CLIENTS ----------------
    with tab1:
        st.subheader("Client Registration")

        col1, col2 = st.columns(2)

        with col1:
            with st.form("client_form"):
                c_name = st.text_input("Full Name")
                c_email = st.text_input("Email")
                c_phone = st.text_input("Phone")
                c_pass = st.text_input("Password", type="password")
                c_allowed_agents = st.text_area("Allowed Agents", height=130)

                if st.form_submit_button("Register", use_container_width=True):
                    try:

                        if not c_allowed_agents.strip():
                            st.error("Allowed Agents JSON cannot be empty")
                            st.stop()

                        c_allowed_agents_dict = json.loads(c_allowed_agents)
                        url = f"{BASE_URL}/clients/add-client"
                        
                        payload = {
                            "client_name": c_name,
                            "client_email": c_email,
                            "phone": c_phone,
                            "password": c_pass,
                            "allowed_agents": c_allowed_agents_dict
                        }
                        res = requests.post(
                            url,
                            json=payload,
                            headers=get_headers()
                        )

                        res.raise_for_status()
                        st.success("Client registered!")

                    except json.JSONDecodeError:
                        st.error("Invalid JSON format for Allowed Agents")
                    except Exception as e:
                        st.error(str(e))

        with col2:
            st.write("### Active Clients")

            try:
                clients = api_get_clients()
                for c in clients:
                    st.text(f"• {c['client_name']} ({c['client_id']})")
            except:
                st.warning("No clients found or endpoint missing")

    # ---------------- CONFIGS ----------------
    with tab2:
        st.subheader("Global YAML Configurations")

        try:
            clients = api_get_clients()
            client_map = {c["client_name"]: c["client_id"] for c in clients}

            selected = st.selectbox("Select Client", list(client_map.keys()))

            if selected:
                client_id = client_map[selected]

                c1, c2 = st.columns(2)

                with c1:
                    config = st.text_area("Upload config json", height=250)

                    if st.button("Save Config") and config:
                        content = json.loads(config)
                        api_create_config(client_id, content)

                        st.success("Config saved!")

                with c2:
                    if st.button("View Config"):
                        config = api_read_config(client_id)
                        st.json(config)


        except Exception as e:
            st.error(str(e))


# MAIN APP ROUTER
def main():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        login_ui()
        return

    user = st.session_state.user_data
    is_super = user["role_name"].lower() == "superadmin"

    with st.sidebar:
        st.title(f"Welcome, {user['user_name']}")
        st.info(f"Role: {user['role_name']}")

        mode = None
        if is_super:
            mode = st.radio("Navigation", ["Assistant", "Management"])
        else:
            mode = "Assistant"

        if st.button("Sign Out", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.token = None
            st.session_state.user_data = None
            st.rerun()

    if is_super and mode == "Management":
        superadmin_ui()
    else:
        assistant_ui(user)


# RUN
if __name__ == "__main__":
    main()