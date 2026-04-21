import re
import streamlit as st
import requests
import time

st.set_page_config(page_title="AMAO", layout="wide")

BASE_URL = "http://localhost:8000"


# =====================================================
# SESSION STATE INIT
# =====================================================
def init_state():
    DEFAULT_STATE = {
        "form_iter": 0,
        "token": None,
        "user_data": None,
        "messages": [],
        "logged_in": False,
        "loaded_client_id": None,
        "cr_agent_rows": [],
        "cr_db_connections": {},
        "cfg_agent_rows": [],
        "cfg_db_connections": {},
        "field_errors": {},
        "cr_no_agent_warning": False,
    }
    for k, v in DEFAULT_STATE.items():
        st.session_state.setdefault(k, v)

init_state()


# =====================================================
# FRONTEND VALIDATORS
# =====================================================
def field_input(label, key, **kwargs):
    """text_input with an inline error caption beneath it."""
    val = st.text_input(label, key=key, **kwargs)
    err = st.session_state.get("field_errors", {}).get(key)
    if err:
        st.caption(f":red[{err}]")
    return val


def err_caption(key):
    """Render an inline red error caption for the given error key if present."""
    err = st.session_state.get("field_errors", {}).get(key)
    if err:
        st.caption(f":red[{err}]")


def validate_client_form(name, email, phone, password, iter):
    errs = {}
    if not name.strip():
        errs[f"c_name_{iter}"] = "Required"
    if not re.match(r"^[^@]+@[^@]+\.[^@]+$", email):
        errs[f"c_email_{iter}"] = "Invalid email"
    if not re.match(r"^\+?\d{7,15}$", phone.replace(" ", "")):
        errs[f"c_phone_{iter}"] = "Invalid phone (7-15 digits)"
    if len(password) < 8:
        errs[f"c_pass_{iter}"] = "Min 8 characters"
    return errs


def validate_temperature(prefix, agent_rows):
    errs = {}
    for i, row in enumerate(agent_rows):
        temp = row.get("temperature")

        if temp is None or not (0 <= temp <= 2):
            errs[f"{prefix}_temp_{i}"] = "Temperature must be between 0 and 2"

    return errs


def validate_top_k(prefix, agent_rows):
    errs = {}
    for i, row in enumerate(agent_rows):
        if row.get("agent") == "rag_agent":
            top_k = row.get("top_k")

            if top_k is None or not (0 < top_k <= 20):
                errs[f"{prefix}_topk_{i}"] = "top_k must be between 1 and 20"

    return errs


def validate_db_connections(prefix, db_connections):
    errs = {}
    for i, dbs in db_connections.items():
        for j, db in enumerate(dbs):
            if db.get("db_type") == "sqlite":
                if not db.get("db_name", "").strip():
                    errs[f"{prefix}_sqlite_{i}_{j}"] = "Required"
            else:
                for field, key in [
                    ("host",     f"{prefix}_h_{i}_{j}"),
                    ("username", f"{prefix}_u_{i}_{j}"),
                    ("password", f"{prefix}_pw_{i}_{j}"),
                    ("db_name",  f"{prefix}_dn_{i}_{j}"),
                ]:
                    if not db.get(field, "").strip():
                        errs[key] = "Required"
                if not db.get("port"):
                    errs[f"{prefix}_p_{i}_{j}"] = "Must be a number"
    return errs


# =====================================================
# DB CONNECTION RENDERER
# =====================================================
def render_db_connections(prefix, i, db_list, agent_type):
    if st.button("➕ Add DB", key=f"{prefix}_add_db_{i}"):
        st.session_state[f"{prefix}_db_connections"].setdefault(i, []).append({})
        st.rerun()

    st.session_state[f"{prefix}_db_connections"].setdefault(i, [{}])
    db_list = st.session_state[f"{prefix}_db_connections"][i]

    for j in range(len(db_list)):
        db = db_list[j]

        # 7 columns (last one for delete button)
        dcols = st.columns([0.8, 1.2, 0.8, 1.2, 1.2, 1.8, 0.4])

        db_type_key = f"{prefix}_db_{i}_{j}"

        # -------------------------
        # DB TYPE
        # -------------------------
        if agent_type == "sql_agent":
            sql_types = ["mysql", "postgres", "mssql", "sqlite", "mariadb"]
            saved_type = db.get("db_type", "mysql")
            saved_index = sql_types.index(saved_type) if saved_type in sql_types else 0
            db_type = dcols[0].selectbox("db_type", sql_types, index=saved_index, key=db_type_key)
        else:
            db_type = dcols[0].selectbox("db_type", ["mongo"], key=db_type_key)

        # Define shared columns
        dbn_col = dcols[5]
        btn_col = dcols[6]

        # -------------------------
        # SQLITE CASE
        # -------------------------
        if agent_type == "sql_agent" and db_type == "sqlite":
            sqlite_key = f"{prefix}_sqlite_{i}_{j}"
            st.session_state.setdefault(sqlite_key, db.get("db_name", ""))

            db_file = dbn_col.text_input("db_file", key=sqlite_key)

            with dbn_col:
                err_caption(sqlite_key)

            st.session_state[f"{prefix}_db_connections"][i][j] = {
                "db_type": "sqlite",
                "db_name": db_file,
            }

        # -------------------------
        # NORMAL DB CASE
        # -------------------------
        else:
            host_key = f"{prefix}_h_{i}_{j}"
            port_key = f"{prefix}_p_{i}_{j}"
            user_key = f"{prefix}_u_{i}_{j}"
            pwd_key  = f"{prefix}_pw_{i}_{j}"
            dbn_key  = f"{prefix}_dn_{i}_{j}"

            st.session_state.setdefault(host_key, db.get("host", ""))
            st.session_state.setdefault(port_key, str(db.get("port", "") or ""))
            st.session_state.setdefault(user_key, db.get("username", ""))
            st.session_state.setdefault(pwd_key,  db.get("password", ""))
            st.session_state.setdefault(dbn_key,  db.get("db_name", ""))

            host = dcols[1].text_input("host", key=host_key)
            port = dcols[2].text_input("port", key=port_key)
            user = dcols[3].text_input("username", key=user_key)
            pwd  = dcols[4].text_input("password", type="password", key=pwd_key)
            dbn  = dbn_col.text_input("db_name", key=dbn_key)

            # Inline errors
            with dcols[1]: err_caption(host_key)
            with dcols[2]: err_caption(port_key)
            with dcols[3]: err_caption(user_key)
            with dcols[4]: err_caption(pwd_key)
            with dbn_col:  err_caption(dbn_key)

            st.session_state[f"{prefix}_db_connections"][i][j] = {
                "db_type":  db_type,
                "host":     host,
                "port":     int(port) if port.isdigit() else None,
                "username": user,
                "password": pwd,
                "db_name":  dbn,
            }

        # -------------------------
        # DELETE BUTTON (for all cases)
        # -------------------------
        if len(db_list) > 1:
            with btn_col:
                st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)

                if st.button("✖", key=f"{prefix}_rm_db_{i}_{j}", help="Delete DB"):
                    st.session_state[f"{prefix}_db_connections"][i].pop(j)
                    st.rerun()


def build_db_payload(db_list):
    clean = []
    for db in db_list:
        if db.get("db_type") == "sqlite":
            clean.append({"db_type": "sqlite", "db_name": db.get("db_name")})
        else:
            clean.append({
                "db_type":  db.get("db_type"),
                "host":     db.get("host"),
                "port":     db.get("port"),
                "username": db.get("username"),
                "password": db.get("password"),
                "db_name":  db.get("db_name"),
            })
    return {f"connection{i+1}": db for i, db in enumerate(clean)}


# =====================================================
# API HELPERS
# =====================================================
def get_headers():
    return {"Authorization": f"Bearer {st.session_state.token}"} if st.session_state.token else {}


def api_request(method, endpoint, *, json=None, data=None, files=None, auth=True, fallback=None):
    try:
        res = requests.request(
            method,
            f"{BASE_URL}{endpoint}",
            json=json,
            data=data,
            files=files,
            headers=get_headers() if auth else {},
        )
        res.raise_for_status()
        return res.json()
    except:
        return fallback if fallback is not None else {}


def api_login(username, password):
    return api_request("POST", "/login", json={"username": username, "password": password})

def api_get_current_user():
    return api_request("GET", "/get-current-user")

def api_chat(query, files=None):
    files_payload = [("files", (f.name, f, f.type)) for f in files] if files else []
    return api_request("POST", "/chat", data={"query": query}, files=files_payload)

def api_get_clients():
    return api_request("GET", "/clients/list-clients").get("data", [])

def api_get_agents():
    return api_request("GET", "/agents/list-agents", fallback={"data": []}).get("data", [])

def api_get_models():
    return api_request("GET", "/models/list-models", fallback={"data": []}).get("data", [])

def api_get_client_config(client_id):
    return api_request("GET", f"/configs/read-config-file/{client_id}") 

# =====================================================
# LOGIN UI
# =====================================================
def login_ui():
    st.markdown("<h1 style='text-align: center;'>AMAO Enterprise Login</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
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
                    st.error(str(e))


# =====================================================
# ASSISTANT UI
# =====================================================
def assistant_ui(user):
    st.title("🤖 Intelligent Assistant")

    # with st.expander("📥 Upload & Index Knowledge"):
    #     files = st.file_uploader("Upload Documents", accept_multiple_files=True)
    #     if st.button("Build Index") and files:
    #         with st.spinner("Processing..."):
    #             api_chat("indexing_request", files)
    #             st.toast("Indexed!", icon="✅")
    
    with st.expander("📥 Upload & Index Knowledge"):

        client_id = st.session_state.user_data.get("client_id")
        print(f"Client id is: {client_id}")
        config = api_get_client_config(client_id)
        print(f"config is: {config}")
        rag_enabled = config.get("allowed_agents", {}).get("rag_agent", {}).get("enabled", False)

        if not rag_enabled:
            st.warning("RAG is not enabled for your client. Contact admin.")
        else:
            files = st.file_uploader("Upload Documents", accept_multiple_files=True)

            if st.button("Build Index") and files:
                with st.spinner("Processing..."):
                    api_chat("indexing_request", files)
                    st.toast("Indexed!", icon="✅")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Ask..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.spinner("Thinking..."):
            res = api_chat(prompt)
            reply = res.get("final_response", "")
            st.session_state.messages.append({"role": "assistant", "content": reply})
            with st.chat_message("assistant"):
                st.markdown(reply)


# =====================================================
# SHARED AGENT EDITOR
# =====================================================
def render_agent_rows(prefix, agent_names, model_names, model_map):
    """Renders agent configuration rows for both create and config tabs."""

    if st.button("➕ Add Agent", key=f"{prefix}_add_agent"):
        st.session_state[f"{prefix}_agent_rows"].append({})
        st.rerun()

    for i in range(len(st.session_state[f"{prefix}_agent_rows"])):
        row = st.session_state[f"{prefix}_agent_rows"][i]
        st.markdown("---")

        # r1, r2 = st.columns([10, 1])
        # r1.markdown("### Agent Configuration")
        # if r2.button("✖", key=f"{prefix}_del_{i}"):
        #     st.session_state[f"{prefix}_agent_rows"].pop(i)
        #     st.session_state[f"{prefix}_db_connections"].pop(i, None)
        #     st.rerun()
        
        header_cols = st.columns([8, 1])

        with header_cols[0]:
            st.markdown("### Agent Configuration")

        with header_cols[1]:
            st.write("")  # small vertical alignment trick
            if st.button("✖", key=f"{prefix}_del_{i}"):
                st.session_state[f"{prefix}_agent_rows"].pop(i)
                st.session_state[f"{prefix}_db_connections"].pop(i, None)
                st.rerun()

        cols = st.columns(3)

        agent = cols[0].selectbox(
            "Agent", agent_names,
            index=agent_names.index(row["agent"]) if row.get("agent") in agent_names else 0,
            key=f"{prefix}_agent_{i}",
        )
        model = cols[1].selectbox(
            "Model", model_names,
            index=model_names.index(row["model"]) if row.get("model") in model_names else 0,
            key=f"{prefix}_model_{i}",
        )
        
        temp_key = f"{prefix}_temp_{i}"
        temp = cols[2].number_input("Temp", value=row.get("temperature", 0.7), key=temp_key)

        with cols[2]:
            err_caption(temp_key)
    
        # temp = cols[2].number_input("Temp", value=row.get("temperature", 0.7), key=f"{prefix}_temp_{i}")

        row_data = {
            "agent":       agent,
            "model":       model,
            "provider":    model_map.get(model, {}).get("provider"),
            "temperature": temp,
        }

        if agent == "rag_agent":
            st.markdown("##### RAG Configuration")
            rcols = st.columns(2)
            
            topk_key = f"{prefix}_topk_{i}"
            row_data["top_k"] = rcols[0].number_input(
                "top_k", min_value=1, step=1,
                value=row.get("top_k", 3),
                key=topk_key,
            )
            with rcols[0]:
                err_caption(topk_key)
                
            row_data["vector_db"] = rcols[1].selectbox(
                "vector_db", ["faiss", "chroma"],
                index=["faiss", "chroma"].index(row.get("vector_db", "faiss")),
                key=f"{prefix}_vdb_{i}",
            )

        if agent in ["sql_agent", "nosql_agent"]:
            st.markdown("##### Database Connections")
            if row.get("agent") != agent:
                st.session_state[f"{prefix}_db_connections"][i] = [{}]
            render_db_connections(prefix, i, st.session_state[f"{prefix}_db_connections"].get(i, []), agent)

        st.session_state[f"{prefix}_agent_rows"][i].update(row_data)


def collect_agent_config(prefix, model_map):
    """Builds the allowed_agents config dict from session state."""
    config = {}
    for i, row in enumerate(st.session_state[f"{prefix}_agent_rows"]):
        agent = row.get("agent")
        model = row.get("model")
        if not agent or not model:
            continue

        base = {
            "model_name":  model,
            "provider":    model_map.get(model, {}).get("provider"),
            "temperature": row.get("temperature", 0.7),
        }

        if agent == "rag_agent":
            base["top_k"]     = row.get("top_k", 3)
            base["vector_db"] = row.get("vector_db", "faiss")

        if agent in ["sql_agent", "nosql_agent"]:
            dbs = st.session_state[f"{prefix}_db_connections"].get(i, [])
            base["database"] = build_db_payload(dbs)

        config[agent] = base
    return config


# =====================================================
# SUPERADMIN UI
# =====================================================
def superadmin_ui():
    st.title("Super Admin Dashboard")

    tab1, tab2 = st.tabs(["Clients", "Configs"])

    agents      = api_get_agents()
    models      = api_get_models()
    agent_names = [a["agent_name"] for a in agents]
    model_names = [m["model_name"] for m in models]
    model_map   = {m["model_name"]: m for m in models}

    # =================================================
    # CLIENT REGISTRATION
    # =================================================
    with tab1:
        st.subheader("Client Registration")
        
        iter = st.session_state.form_iter

        c_name  = field_input("Full Name", f"c_name_{iter}")
        c_email = field_input("Email",     f"c_email_{iter}")
        c_phone = field_input("Phone",     f"c_phone_{iter}")
        c_pass  = field_input("Password",  f"c_pass_{iter}", type="password")

        render_agent_rows("cr", agent_names, model_names, model_map)

        if st.session_state.get("cr_no_agent_warning"):
            st.warning("Please add at least one agent before registering.")
        
        
        if st.button("Register", use_container_width=True):
            # 1. Check if rows actually exist
            no_agents = not st.session_state.cr_agent_rows
            
            # 2. Field Validations (Name, Email, etc.)
            iter = st.session_state.form_iter
            field_errs = validate_client_form(c_name, c_email, c_phone, c_pass, iter)
            
            # 3. Targeted DB Validation
            # Only validate DB connections for rows where the agent is SQL or NoSQL
            relevant_db_errs = {}
            for i, row in enumerate(st.session_state.cr_agent_rows):
                agent_type = row.get("agent")
                if agent_type in ["sql_agent", "nosql_agent"]:
                    # Only validate if this specific row index has DB data
                    specific_db_data = {i: st.session_state.cr_db_connections.get(i, [{}])}
                    relevant_db_errs.update(validate_db_connections("cr", specific_db_data))
            
            temp_errs = validate_temperature("cr", st.session_state.cr_agent_rows)
            topk_errs = validate_top_k("cr", st.session_state.cr_agent_rows)

            all_errs = {**field_errs, **relevant_db_errs, **temp_errs, **topk_errs}
            
            st.session_state.field_errors = all_errs
            st.session_state["cr_no_agent_warning"] = no_agents
            
            if all_errs or no_agents:
                st.rerun()

            # 4. API Call
            if not all_errs and not no_agents:
                payload = {
                    "client_name":   c_name,
                    "client_email":  c_email,
                    "phone":         c_phone,
                    "password":      c_pass,
                    "allowed_agents": collect_agent_config("cr", model_map),
                }
                
                try:
                    res = requests.post(
                        f"{BASE_URL}/clients/add-client", 
                        json=payload, 
                        headers=get_headers(),
                        timeout=10
                    )
                    if res.ok:
                        st.success("Client registered successfully! ✅")
                        
                        st.session_state.form_iter += 1
                        # Reset states
                        st.session_state.cr_agent_rows = []
                        st.session_state.cr_db_connections = {}
                        st.session_state.field_errors = {}
                        st.session_state["cr_no_agent_warning"] = False
                        time.sleep(2)
                        st.rerun()
                    else:
                        error_data = res.json()
                        st.error(f"Registration failed: {error_data.get('detail', 'Unknown error')}")
                except Exception as e:
                    st.error(f"Connection Error: {e}")

    # =================================================
    # CONFIG TAB
    # =================================================
    with tab2:
        st.subheader("Global Configs")

        clients  = api_get_clients()
        cmap     = {c["client_name"]: c["client_id"] for c in clients}

        c1, c2   = st.columns([3, 1], vertical_alignment="bottom")
        selected = c1.selectbox("Client", list(cmap.keys()))

        if selected:
            cid = cmap[selected]
            if st.session_state.loaded_client_id != cid:
                st.session_state.cfg_agent_rows    = []
                st.session_state.cfg_db_connections = {}
                st.session_state.loaded_client_id  = None

        st.markdown("<div style='height: 38px;'></div>", unsafe_allow_html=True)

        if c2.button("View / Update Config", key="cfg_load_btn") and selected:
            cid = cmap[selected]
            res = requests.get(f"{BASE_URL}/configs/read-config-file/{cid}", headers=get_headers())
            res.raise_for_status()

            allowed_agents = res.json().get("allowed_agents", {})
            st.session_state.cfg_agent_rows    = []
            st.session_state.cfg_db_connections = {}

            for i, (agent_name, cfg) in enumerate(allowed_agents.items()):
                row = {
                    "agent":       agent_name,
                    "model":       cfg.get("model_name"),
                    "provider":    cfg.get("provider"),
                    "temperature": cfg.get("temperature", 0.7),
                }
                if "top_k"     in cfg: row["top_k"]     = cfg["top_k"]
                if "vector_db" in cfg: row["vector_db"] = cfg["vector_db"]
                if "database"  in cfg:
                    st.session_state.cfg_db_connections[i] = list(cfg["database"].values())

                st.session_state.cfg_agent_rows.append(row)

            st.session_state.loaded_client_id = cid
            st.toast("Config loaded!", icon="✅")

        if selected and st.session_state.loaded_client_id == cmap.get(selected):
            st.markdown("### Edit Configuration")
            render_agent_rows("cfg", agent_names, model_names, model_map)

            if st.button("Update Config", key="cfg_update_btn"):
                
                db_errs   = validate_db_connections("cfg", st.session_state.cfg_db_connections)
                temp_errs = validate_temperature("cfg", st.session_state.cfg_agent_rows)
                topk_errs = validate_top_k("cfg", st.session_state.cfg_agent_rows)

                errs = {**db_errs, **temp_errs, **topk_errs}
                
                st.session_state.field_errors = errs
                if not errs:
                    cid = cmap[selected]
                    res = requests.put(
                        f"{BASE_URL}/configs/update-config-file/{cid}",
                        json={"allowed_agents": collect_agent_config("cfg", model_map)},
                        headers=get_headers(),
                    )
                    if res.ok:
                        st.toast("Config updated successfully!", icon="✅")
                        st.session_state.field_errors = {}
                        time.sleep(2)
                    else:
                        st.error(f"Update failed: {res.text}")
                st.rerun()


# =====================================================
# MAIN
# =====================================================
def main():
    if not st.session_state.logged_in:
        login_ui()
        return

    user     = st.session_state.user_data
    is_super = user["role_name"].lower() == "superadmin"

    with st.sidebar:
        st.title(f"Welcome {user['user_name']}")
        st.info(user["role_name"])

        mode = "Assistant"
        if is_super:
            mode = st.radio("Navigation", ["Assistant", "Management"])

        if st.button("Sign Out"):
            st.session_state.clear()
            st.rerun()

    if is_super and mode == "Management":
        superadmin_ui()
    else:
        assistant_ui(user)


if __name__ == "__main__":
    main()