import re
import streamlit as st
import requests
import time
import copy
import json

st.set_page_config(page_title="AMAO", layout="wide")

BASE_URL = "http://localhost:8000"


# ====================
# SESSION STATE INIT
# ====================
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

def validate_api_keys(prefix, agent_rows):
    errs = {}

    for i, row in enumerate(agent_rows):
        provider = row.get("provider")
        api_key = row.get("api_key")

        if provider != "self_hosted":
            if not api_key or not api_key.strip():
                errs[f"{prefix}_apikey_{i}"] = "API key required"

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

def validate_vector_db(prefix, agent_rows):
    errs = {}

    for i, row in enumerate(agent_rows):
        vdb = row.get("vector_db")

        if not isinstance(vdb, dict):
            continue

        provider = vdb.get("provider")
        cfg = vdb.get("config", {}) or {}

        # -------------------------
        # PINECONE VALIDATION
        # -------------------------
        if provider == "pinecone":
            if not cfg.get("vectordb_api_key"):
                errs[f"{prefix}_pine_key_{i}"] = "Required"
            if not cfg.get("index_name"):
                errs[f"{prefix}_pine_index_{i}"] = "Required"

        # -------------------------
        # CHROMA CLOUD VALIDATION
        # -------------------------
        if provider == "chroma cloud":
            if not cfg.get("vectordb_api_key"):
                errs[f"{prefix}_chroma_key_{i}"] = "Required"
            if not cfg.get("tenant_id"):
                errs[f"{prefix}_chroma_tenant_{i}"] = "Required"
            if not cfg.get("database"):
                errs[f"{prefix}_chroma_db_{i}"] = "Required"
            if not cfg.get("collection_name"):
                errs[f"{prefix}_chroma_collection_{i}"] = "Required"

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
        # DELETE BUTTON
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
    all_models = []
    page = 1
    size = 50

    while True:
        res = api_request("GET", f"/models/list-models?page={page}&size={size}", fallback={"data": [], "total": 0})

        data = res.get("data", [])
        total = res.get("total", 0)

        all_models.extend(data)

        if len(all_models) >= total:
            break

        page += 1

    return all_models

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
    
    with st.expander("📥 Upload & Index Knowledge"):

        client_id = st.session_state.user_data.get("client_id")
        config = api_get_client_config(client_id)
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

    # -------------------------
    # BUILD PROVIDER LIST
    # -------------------------
    providers = list(set([m.get("provider") for m in model_map.values() if m.get("provider")]))

    for i in range(len(st.session_state[f"{prefix}_agent_rows"])):
        row = st.session_state[f"{prefix}_agent_rows"][i]
        st.markdown("---")

        header_cols = st.columns([8, 1])

        with header_cols[0]:
            st.markdown("### Agent Configuration")

        with header_cols[1]:
            st.write("")
            if st.button("✖", key=f"{prefix}_del_{i}"):
                st.session_state[f"{prefix}_agent_rows"].pop(i)
                st.session_state[f"{prefix}_db_connections"].pop(i, None)
                st.rerun()

        # -------------------------
        # ADD PROVIDER COLUMN
        # -------------------------
        cols = st.columns(5)

        # -------------------------
        # AGENT
        # -------------------------
        agent = cols[0].selectbox(
            "Agent", agent_names,
            index=agent_names.index(row["agent"]) if row.get("agent") in agent_names else 0,
            key=f"{prefix}_agent_{i}",
        )

        # -------------------------
        # PROVIDER
        # -------------------------
        provider = cols[1].selectbox(
            "Provider",
            providers,
            index=providers.index(row["provider"]) if row.get("provider") in providers else 0,
            key=f"{prefix}_provider_{i}",
        )
        
        api_key_key = f"{prefix}_apikey_{i}"

        # CLEAR API KEY IF SELF HOSTED
        if provider == "self_hosted":
            st.session_state[api_key_key] = None

        # -------------------------
        # FILTER MODELS BY PROVIDER
        # -------------------------
        filtered_models = [
            m for m in model_names
            if model_map.get(m, {}).get("provider") == provider
        ]

        # fallback safety
        if not filtered_models:
            filtered_models = model_names

        # -------------------------
        # MODEL
        # -------------------------
        model = cols[2].selectbox(
            "Model",
            filtered_models,
            index=filtered_models.index(row["model"]) if row.get("model") in filtered_models else 0,
            key=f"{prefix}_model_{i}",
        )
        
        # -------------------------
        # API KEY (ONLY NON-SELF HOSTED)
        # -------------------------
        api_key = None
        api_key_key = f"{prefix}_apikey_{i}"

        if provider != "self_hosted":
            api_key = cols[3].text_input(
                "API Key",
                value=row.get("api_key", ""),
                type="password",
                key=api_key_key
            )

            with cols[3]:
                err_caption(api_key_key)
            
        else:
            with cols[3]:
                st.markdown("<div style='height: 36px;'></div>", unsafe_allow_html=True)
                st.caption("🔒 Self-hosted (no API key needed)")

        # -------------------------
        # TEMPERATURE
        # -------------------------
        temp_key = f"{prefix}_temp_{i}"
        temp = cols[4].number_input(
            "Temp",
            value=row.get("temperature", 0.7),
            key=temp_key
        )

        with cols[4]:
            err_caption(temp_key)

        # -------------------------
        # STORE DATA
        # -------------------------
        row_data = {
            "agent":       agent,
            "model":       model,
            "provider":    provider,
            "temperature": temp,
            "api_key":     api_key if provider != "self_hosted" else None,
        }


        # -------------------------
        # RAG CONFIG
        # -------------------------
        if agent == "rag_agent":
            st.markdown("##### RAG Configuration")

            rcols = st.columns([1, 1, 1, 1, 1, 1], gap="small")

            topk_key = f"{prefix}_topk_{i}"
            row_data["top_k"] = rcols[0].number_input(
                "top_k", min_value=1, step=1,
                value=row.get("top_k", 3),
                key=topk_key,
            )
            with rcols[0]:
                err_caption(topk_key)

            vdb_options = ["faiss", "chroma local", "chroma cloud", "pinecone"]

            current_vdb = row.get("vector_db")
            if isinstance(current_vdb, dict):
                current_vdb = current_vdb.get("provider")

            index = vdb_options.index(current_vdb) if current_vdb in vdb_options else 0

            vector_db = rcols[1].selectbox(
                "vector_db",
                vdb_options,
                index=index,
                key=f"{prefix}_vdb_{i}",
            )

            vectordb_payload = {"provider": vector_db}

            # -------------------------
            # CHROMA LOCAL
            # -------------------------
            if vector_db == "chroma local":
                vectordb_payload["config"] = {"mode": "local"}

                for col in rcols[2:]:
                    with col:
                        st.empty()

            # -------------------------
            # CHROMA CLOUD
            # -------------------------
            elif vector_db == "chroma cloud":

                chroma_cfg = row.get("vector_db", {}).get("config", {})

                chroma_api_key = rcols[2].text_input(
                    "Chroma API Key",
                    type="password",
                    value=chroma_cfg.get("vectordb_api_key", ""),
                    key=f"{prefix}_chroma_key_{i}"
                )
                
                with rcols[2]: err_caption(f"{prefix}_chroma_key_{i}") 

                tenant_id = rcols[3].text_input(
                    "Tenant ID",
                    value=chroma_cfg.get("tenant", ""),
                    key=f"{prefix}_chroma_tenant_{i}"
                )
                
                with rcols[3]: err_caption(f"{prefix}_chroma_tenant_{i}")

                database_name = rcols[4].text_input(
                    "Database",
                    value=chroma_cfg.get("database", ""),
                    key=f"{prefix}_chroma_db_{i}"
                )
                
                with rcols[4]: err_caption(f"{prefix}_chroma_db_{i}")

                collection_name = rcols[5].text_input(
                    "Collection",
                    value=chroma_cfg.get("collection_name", ""),
                    key=f"{prefix}_chroma_collection_{i}"
                )
                
                with rcols[5]: err_caption(f"{prefix}_chroma_collection_{i}")

                vectordb_payload["config"] = {
                    "mode": "cloud",
                    "vectordb_api_key": chroma_api_key,
                    "tenant_id": tenant_id,
                    "database": database_name,
                    "collection_name": collection_name
                }

            # -------------------------
            # PINECONE
            # -------------------------
            elif vector_db == "pinecone":

                pine_config = row.get("vector_db", {}).get("config", {})

                pine_key = rcols[2].text_input(
                    "Pinecone API Key",
                    type="password",
                    value=pine_config.get("vectordb_api_key", ""),
                    key=f"{prefix}_pine_key_{i}"
                )
                
                with rcols[2]: err_caption(f"{prefix}_pine_key_{i}")

                index_name = rcols[3].text_input(
                    "Index Name",
                    value=pine_config.get("index_name", ""),
                    key=f"{prefix}_pine_index_{i}"
                )
                
                with rcols[3]: err_caption(f"{prefix}_pine_index_{i}")

                for col in rcols[4:]:
                    with col:
                        st.empty()

                vectordb_payload["config"] = {
                    "vectordb_api_key": pine_key,
                    "index_name": index_name
                }

            # -------------------------
            # FAISS
            # -------------------------
            else:
                for col in rcols[2:]:
                    with col:
                        st.empty()

            row_data["vector_db"] = vectordb_payload
        

        # -------------------------
        # DB CONFIG
        # -------------------------
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
            "provider": row.get("provider"),
            "temperature": row.get("temperature", 0.7),
        }
        
        if row.get("provider") != "self_hosted":
            base["api_key"] = row.get("api_key")

        if agent == "rag_agent":
            base["top_k"] = row.get("top_k", 3)

            vdb = row.get("vector_db")

            if not isinstance(vdb, dict):
                base["vector_db"] = {
                    "provider": vdb,
                    "config": {}
                }
            else:
                provider = vdb.get("provider")
                vdb_cfg = copy.deepcopy(vdb.get("config", {}))

                if provider == "chroma local":
                    base["vector_db"] = {
                        "provider": "chroma",
                        "config": {
                            "mode": "local"
                        }
                    }

                elif provider == "chroma cloud":
                    base["vector_db"] = {
                        "provider": "chroma",
                        "config": {
                            "mode": "cloud",
                            **vdb_cfg
                        }
                    }

                else:
                    base["vector_db"] = copy.deepcopy(vdb)
            
        
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
            no_agents = not st.session_state.cr_agent_rows
            
            iter = st.session_state.form_iter
            field_errs = validate_client_form(c_name, c_email, c_phone, c_pass, iter)
            
            relevant_db_errs = {}
            for i, row in enumerate(st.session_state.cr_agent_rows):
                agent_type = row.get("agent")
                if agent_type in ["sql_agent", "nosql_agent"]:
                    # Only validate if this specific row index has DB data
                    specific_db_data = {i: st.session_state.cr_db_connections.get(i, [{}])}
                    relevant_db_errs.update(validate_db_connections("cr", specific_db_data))
            
            temp_errs = validate_temperature("cr", st.session_state.cr_agent_rows)
            topk_errs = validate_top_k("cr", st.session_state.cr_agent_rows)

            api_errs = validate_api_keys("cr", st.session_state.cr_agent_rows)
            vdb_errs = validate_vector_db("cr", st.session_state.cr_agent_rows)

            all_errs = {**field_errs, **relevant_db_errs, **temp_errs, **topk_errs, **api_errs, **vdb_errs}
            
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
                    "api_key":     cfg.get("api_key")
                }
                if "top_k"     in cfg: row["top_k"]     = cfg["top_k"]

                if "vector_db" in cfg:
                    vdb = cfg["vector_db"]

                    if isinstance(vdb, str):
                        row["vector_db"] = {"provider": vdb, "config": {}}
                    else:
                        provider = vdb.get("provider")

                        # normalize UI mapping
                        if provider == "faiss":
                            ui_provider = "faiss"
                        elif provider == "pinecone":
                            ui_provider = "pinecone"
                        elif provider == "chroma":
                            mode = vdb.get("config", {}).get("mode", "local")
                            ui_provider = "chroma cloud" if mode == "cloud" else "chroma local"
                        else:
                            ui_provider = provider

                        row["vector_db"] = {
                            "provider": ui_provider,
                            "config": vdb.get("config", {})
                        }
        
                if "database"  in cfg:
                    # st.session_state.cfg_db_connections[i] = list(cfg["database"].values())
                    st.session_state.cfg_db_connections[i] = [
                        dict(db) for db in cfg["database"].values()
                    ]

                st.session_state.cfg_agent_rows.append(row)

            st.session_state.loaded_client_id = cid
            st.toast("Config loaded!", icon="✅")

        if selected and st.session_state.loaded_client_id == cmap.get(selected):
            st.markdown("### Edit Configuration")
            render_agent_rows("cfg", agent_names, model_names, model_map)

            if st.button("Update Config", key="cfg_update_btn"):

                relevant_db_errs = {}

                for i, row in enumerate(st.session_state.cfg_agent_rows):
                    agent_type = row.get("agent")

                    if agent_type in ["sql_agent", "nosql_agent"]:
                        specific_db_data = {
                            i: st.session_state.cfg_db_connections.get(i, [{}])
                        }
                        relevant_db_errs.update(
                            validate_db_connections("cfg", specific_db_data)
                        )

                temp_errs = validate_temperature("cfg", st.session_state.cfg_agent_rows)
                topk_errs = validate_top_k("cfg", st.session_state.cfg_agent_rows)
                api_errs  = validate_api_keys("cfg", st.session_state.cfg_agent_rows)
                vdb_errs = validate_vector_db("cfg", st.session_state.cfg_agent_rows)

                errs = {**relevant_db_errs, **temp_errs, **topk_errs, **api_errs, **vdb_errs}
                
                st.session_state.field_errors = errs
                
                if errs:
                    st.session_state.field_errors = errs
                    st.rerun()

                cid = cmap[selected]

                res = requests.put(
                    f"{BASE_URL}/configs/update-config-file/{cid}",
                    json={"allowed_agents": collect_agent_config("cfg", model_map)},
                    headers=get_headers(),
                )

                if res.ok:
                    st.toast("Config updated successfully!", icon="✅")
                    st.session_state.field_errors = {}
                    time.sleep(1)
                    st.rerun()

                else:
                    try:
                        error_msg = res.json().get("detail", res.text)
                    except:
                        error_msg = res.text

                    st.error(f"Update failed: {error_msg}")


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