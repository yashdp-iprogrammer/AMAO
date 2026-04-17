import streamlit as st
import requests

st.set_page_config(page_title="AMAO", layout="wide")

BASE_URL = "http://localhost:8000"


# =====================================================
# SESSION STATE INIT
# =====================================================
if "token" not in st.session_state:
    st.session_state.token = None

if "user_data" not in st.session_state:
    st.session_state.user_data = None

if "messages" not in st.session_state:
    st.session_state.messages = []

if "agent_rows" not in st.session_state:
    st.session_state.agent_rows = []

if "db_connections" not in st.session_state:
    st.session_state.db_connections = {}

if "form_errors" not in st.session_state:
    st.session_state.form_errors = {}

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# ✅ NEW FIX
if "loaded_client_id" not in st.session_state:
    st.session_state.loaded_client_id = None
    

# CLIENT REGISTRATION STATE
if "cr_agent_rows" not in st.session_state:
    st.session_state.cr_agent_rows = []

if "cr_db_connections" not in st.session_state:
    st.session_state.cr_db_connections = {}

# CONFIG TAB STATE
if "cfg_agent_rows" not in st.session_state:
    st.session_state.cfg_agent_rows = []

if "cfg_db_connections" not in st.session_state:
    st.session_state.cfg_db_connections = {}


# =====================================================
# ERROR PARSER
# =====================================================
def parse_fastapi_error(res):
    try:
        data = res.json()
    except Exception:
        return {"_global": res.text}

    errors = {}

    if "detail" in data:
        for err in data["detail"]:
            loc = err.get("loc", [])
            field = loc[-1] if loc else "_global"
            errors[field] = err.get("msg", "Invalid value")

    return errors


# =====================================================
# API HELPERS
# =====================================================
def get_headers():
    return {"Authorization": f"Bearer {st.session_state.token}"} if st.session_state.token else {}


def api_login(username, password):
    res = requests.post(
        f"{BASE_URL}/login",
        json={"username": username, "password": password}
    )
    res.raise_for_status()
    return res.json()


def api_get_current_user():
    res = requests.get(f"{BASE_URL}/get-current-user", headers=get_headers())
    res.raise_for_status()
    return res.json()


def api_chat(query, files=None):
    files_payload = []
    if files:
        for f in files:
            files_payload.append(("files", (f.name, f, f.type)))

    res = requests.post(
        f"{BASE_URL}/chat",
        data={"query": query},
        files=files_payload,
        headers=get_headers()
    )
    res.raise_for_status()
    return res.json()


def api_get_clients():
    res = requests.get(f"{BASE_URL}/clients/list-clients", headers=get_headers())
    return res.json().get("data", [])


def api_get_agents():
    try:
        res = requests.get(f"{BASE_URL}/agents/list-agents", headers=get_headers())
        res.raise_for_status()
        return res.json().get("data", [])
    except:
        return []


def api_get_models():
    try:
        res = requests.get(f"{BASE_URL}/models/list-models", headers=get_headers())
        res.raise_for_status()
        return res.json().get("data", [])
    except:
        return []


def api_create_config(client_id, config):
    res = requests.post(
        f"{BASE_URL}/configs/create-config-file/{client_id}",
        json=config,
        headers=get_headers()
    )
    res.raise_for_status()
    return res.json()


def api_read_config(client_id):
    res = requests.get(f"{BASE_URL}/configs/read-config/{client_id}", headers=get_headers())
    return res.json()


# =====================================================
# LOGIN UI
# =====================================================
def login_ui():
    st.markdown("<h1 style='text-align: center;'>🚀 AMAO Enterprise Login</h1>", unsafe_allow_html=True)

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
        files = st.file_uploader("Upload Documents", accept_multiple_files=True)

        if st.button("Build Index") and files:
            with st.spinner("Processing..."):
                api_chat("indexing_request", files)
                st.success("Indexed!")

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
# SUPERADMIN UI
# =====================================================
def superadmin_ui():
    st.title("🛠️ Super Admin Dashboard")

    tab1, tab2 = st.tabs(["🏢 Clients", "⚙️ Configs"])

    # =================================================
    # CLIENT REGISTRATION (FINAL STABLE VERSION)
    # =================================================
    with tab1:
        st.subheader("Client Registration")

        agents = api_get_agents()
        models = api_get_models()

        agent_names = [a["agent_name"] for a in agents]
        model_names = [m["model_name"] for m in models]
        model_map = {m["model_name"]: m for m in models}

        c_name = st.text_input("Full Name")
        c_email = st.text_input("Email")
        c_phone = st.text_input("Phone")
        c_pass = st.text_input("Password", type="password")

        st.markdown("### Allowed Agents")

        # ADD AGENT
        if st.button("➕ Add Agent", key="cr_add_agent"):
            st.session_state.cr_agent_rows.append({"id": len(st.session_state.cr_agent_rows)})

        # =============================
        # AGENT LOOP
        # =============================
        for i, row in enumerate(st.session_state.cr_agent_rows):

            st.markdown("---")

            r1, r2 = st.columns([10, 1])
            with r1:
                st.markdown("### Agent Configuration")
            with r2:
                if st.button("✖", key=f"cr_del_{i}"):
                    st.session_state.cr_agent_rows.pop(i)
                    st.session_state.cr_db_connections.pop(i, None)
                    st.rerun()

            # ---------------------------
            # STABLE DEFAULT VALUES
            # ---------------------------
            agent_key = f"cr_agent_{i}"
            model_key = f"cr_model_{i}"
            temp_key = f"cr_temp_{i}"

            if agent_key not in st.session_state:
                st.session_state[agent_key] = agent_names[0] if agent_names else None

            if model_key not in st.session_state:
                st.session_state[model_key] = model_names[0] if model_names else None

            if temp_key not in st.session_state:
                st.session_state[temp_key] = 0.7

            cols = st.columns(3)

            agent = cols[0].selectbox("Agent", agent_names, key=agent_key)
            model = cols[1].selectbox("Model", model_names, key=model_key)
            temp = cols[2].number_input("Temp", key=temp_key)

            provider = model_map.get(model, {}).get("provider")

            # =============================
            # RAG
            # =============================
            if agent == "rag_agent":
                st.markdown("##### RAG Configuration")

                topk_key = f"cr_topk_{i}"
                vdb_key = f"cr_vdb_{i}"

                if topk_key not in st.session_state:
                    st.session_state[topk_key] = 3

                if vdb_key not in st.session_state:
                    st.session_state[vdb_key] = "faiss"

                rcols = st.columns(2)

                # rcols[0].number_input("top_k", key=topk_key)
                rcols[0].number_input(
                    "top_k",
                    min_value=1,
                    step=1,
                    # value=int(st.session_state.get(topk_key, 3)),
                    key=topk_key
                )
                rcols[1].selectbox("vector_db", ["faiss", "chroma"], key=vdb_key)

            # =============================
            # SQL AGENT
            # =============================
            elif agent == "sql_agent":
                st.markdown("##### Database Connections")

                if st.button("➕ Add DB", key=f"cr_add_db_{i}"):
                    st.session_state.cr_db_connections.setdefault(i, []).append({})

                st.session_state.cr_db_connections.setdefault(i, [{}])
                db_list = st.session_state.cr_db_connections[i]

                for j in range(len(db_list)):

                    db = db_list[j]

                    dcols = st.columns([1,1,1,1,1,1,0.5])

                    db_key = f"cr_db_{i}_{j}"
                    host_key = f"cr_h_{i}_{j}"
                    port_key = f"cr_p_{i}_{j}"
                    user_key = f"cr_u_{i}_{j}"
                    pwd_key = f"cr_pw_{i}_{j}"
                    dbn_key = f"cr_dn_{i}_{j}"

                    # defaults
                    st.session_state.setdefault(db_key, db.get("db_type", "mysql"))
                    st.session_state.setdefault(host_key, db.get("host", ""))
                    st.session_state.setdefault(port_key, str(db.get("port", "")))
                    st.session_state.setdefault(user_key, db.get("username", ""))
                    st.session_state.setdefault(pwd_key, db.get("password", ""))
                    st.session_state.setdefault(dbn_key, db.get("db_name", ""))

                    db_type = dcols[0].selectbox(
                        "db_type",
                        ["mysql","postgres","mssql","sqlite","mariadb"],
                        key=db_key
                    )

                    host = dcols[1].text_input("host", key=host_key)
                    port = dcols[2].text_input("port", key=port_key)
                    user = dcols[3].text_input("username", key=user_key)
                    pwd = dcols[4].text_input("password", type="password", key=pwd_key)
                    dbn = dcols[5].text_input("db_name", key=dbn_key)

                    with dcols[6]:
                        if len(db_list) > 1:
                            if st.button("✖", key=f"cr_rm_db_{i}_{j}"):
                                st.session_state.cr_db_connections[i].pop(j)
                                st.rerun()

                    st.session_state.cr_db_connections[i][j] = {
                        "db_type": db_type,
                        "host": host,
                        "port": int(port) if port.isdigit() else None,
                        "username": user,
                        "password": pwd,
                        "db_name": dbn
                    }

            # =============================
            # NOSQL AGENT 
            # =============================
            elif agent == "nosql_agent":
                st.markdown("##### Database Connections")

                # ➕ ADD DB BUTTON
                if st.button("➕ Add DB", key=f"cr_add_nosql_db_{i}"):
                    st.session_state.cr_db_connections.setdefault(i, []).append({})

                # Ensure at least 1 connection exists
                st.session_state.cr_db_connections.setdefault(i, [{}])
                db_list = st.session_state.cr_db_connections[i]

                for j in range(len(db_list)):

                    db = db_list[j]

                    dcols = st.columns([1,1,1,1,1,1,0.5])

                    # Keys
                    ndb_key = f"cr_ndb_{i}_{j}"
                    nh_key = f"cr_nh_{i}_{j}"
                    np_key = f"cr_np_{i}_{j}"
                    nu_key = f"cr_nu_{i}_{j}"
                    npw_key = f"cr_npw_{i}_{j}"
                    nd_key = f"cr_nd_{i}_{j}"

                    # Defaults
                    st.session_state.setdefault(ndb_key, db.get("db_type", "mongo"))
                    st.session_state.setdefault(nh_key, db.get("host", ""))
                    st.session_state.setdefault(np_key, str(db.get("port", "")))
                    st.session_state.setdefault(nu_key, db.get("username", ""))
                    st.session_state.setdefault(npw_key, db.get("password", ""))
                    st.session_state.setdefault(nd_key, db.get("db_name", ""))

                    # Inputs
                    db_type = dcols[0].selectbox("db_type", ["mongo"], key=ndb_key)
                    host = dcols[1].text_input("host", key=nh_key)
                    port = dcols[2].text_input("port", key=np_key)
                    user = dcols[3].text_input("username", key=nu_key)
                    pwd = dcols[4].text_input("password",  type="password", key=npw_key)
                    dbn = dcols[5].text_input("db_name", key=nd_key)

                    # ❌ REMOVE BUTTON (only if >1)
                    with dcols[6]:
                        if len(db_list) > 1:
                            if st.button("✖", key=f"cr_rm_nosql_db_{i}_{j}"):
                                st.session_state.cr_db_connections[i].pop(j)
                                st.rerun()

                    # Save back
                    st.session_state.cr_db_connections[i][j] = {
                        "db_type": db_type,
                        "host": host,
                        "port": int(port) if port.isdigit() else None,
                        "username": user,
                        "password": pwd,
                        "db_name": dbn
                    }

        # =============================
        # SUBMIT
        # =============================
        if st.button("Register", use_container_width=True):

            config = {}

            for i in range(len(st.session_state.cr_agent_rows)):

                agent = st.session_state.get(f"cr_agent_{i}")
                model = st.session_state.get(f"cr_model_{i}")
                temp = st.session_state.get(f"cr_temp_{i}", 0.7)

                if not agent or not model:
                    continue

                base = {
                    "model_name": model,
                    "provider": model_map.get(model, {}).get("provider"),
                    "temperature": temp
                }

                if agent == "rag_agent":
                    base["top_k"] = st.session_state.get(f"cr_topk_{i}", 3)
                    base["vector_db"] = st.session_state.get(f"cr_vdb_{i}", "faiss")

                if agent in ["sql_agent", "nosql_agent"]:
                    dbs = st.session_state.cr_db_connections.get(i, [])
                    base["database"] = {
                        f"connection{idx+1}": db for idx, db in enumerate(dbs)
                    }

                config[agent] = base

            payload = {
                "client_name": c_name,
                "client_email": c_email,
                "phone": c_phone,
                "password": c_pass,
                "allowed_agents": config
            }

            res = requests.post(
                f"{BASE_URL}/clients/add-client",
                json=payload,
                headers=get_headers()
            )

            if not res.ok:
                st.error(res.text)
                return

            st.success("Client registered successfully!")

            # RESET ONLY THIS TAB
            st.session_state.cr_agent_rows = []
            st.session_state.cr_db_connections = {}

    # =================================================
    # CONFIG TAB (FIXED)
    # =================================================
    with tab2:
        st.subheader("Global Configs")

        clients = api_get_clients()
        cmap = {c["client_name"]: c["client_id"] for c in clients}

        c1, c2 = st.columns([3, 1])

        with c1:
            selected = st.selectbox("Client", list(cmap.keys()))

        with c2:
            load_btn = st.button("View / Update Config", key="cfg_load_btn")

        # RESET ON CLIENT CHANGE
        if selected:
            cid = cmap[selected]
            if st.session_state.loaded_client_id != cid:
                st.session_state.cfg_agent_rows = []
                st.session_state.cfg_db_connections = {}
                st.session_state.loaded_client_id = None

        # LOAD CONFIG
        if load_btn and selected:
            cid = cmap[selected]

            res = requests.get(
                f"{BASE_URL}/clients/get-client/{cid}",
                headers=get_headers()
            )
            res.raise_for_status()
            client_data = res.json()

            allowed_agents = client_data.get("allowed_agents", {})

            st.session_state.cfg_agent_rows = []
            st.session_state.cfg_db_connections = {}

            for i, (agent_name, cfg) in enumerate(allowed_agents.items()):
                row = {
                    "agent": agent_name,
                    "model": cfg.get("model_name"),
                    "provider": cfg.get("provider"),
                    "temperature": cfg.get("temperature", 0.7)
                }

                if "top_k" in cfg:
                    row["top_k"] = cfg.get("top_k")

                if "vector_db" in cfg:
                    row["vector_db"] = cfg.get("vector_db")

                if "database" in cfg:
                    st.session_state.cfg_db_connections[i] = list(cfg["database"].values())

                st.session_state.cfg_agent_rows.append(row)

            st.session_state.loaded_client_id = cid
            st.success("Config loaded!")

        # RENDER
        if (
            selected
            and st.session_state.loaded_client_id == cmap[selected]
        ):
            st.markdown("### Edit Configuration")

            agents = api_get_agents()
            models = api_get_models()

            agent_names = [a["agent_name"] for a in agents]
            model_names = [m["model_name"] for m in models]
            model_map = {m["model_name"]: m for m in models}

            # ➕ ADD AGENT
            if st.button("➕ Add Agent", key="cfg_add_agent"):
                st.session_state.cfg_agent_rows.append({
                    "agent": agent_names[0] if agent_names else None,
                    "model": model_names[0] if model_names else None,
                    "provider": None,
                    "temperature": 0.7
                })
                st.rerun()

            # LOOP
            for i in range(len(st.session_state.cfg_agent_rows)):
                st.markdown("---")

                row = st.session_state.cfg_agent_rows[i]

                r1, r2 = st.columns([10, 1])

                with r1:
                    st.markdown("### Agent Configuration")

                with r2:
                    if st.button("✖", key=f"cfg_del_{i}"):
                        st.session_state.cfg_agent_rows.pop(i)
                        st.session_state.cfg_db_connections.pop(i, None)
                        st.rerun()

                cols = st.columns(3)

                # SAFE SELECTBOXES
                agent = cols[0].selectbox(
                    "Agent",
                    agent_names,
                    index=agent_names.index(row["agent"]) if row.get("agent") in agent_names else 0,
                    key=f"cfg_agent_{i}"
                )

                model = cols[1].selectbox(
                    "Model",
                    model_names,
                    index=model_names.index(row["model"]) if row.get("model") in model_names else 0,
                    key=f"cfg_model_{i}"
                )

                provider = model_map.get(model, {}).get("provider")

                temp = cols[2].number_input(
                    "Temp",
                    value=row.get("temperature", 0.7),
                    key=f"cfg_temp_{i}"
                )

                # RESET DB IF AGENT TYPE CHANGES
                prev_agent = row.get("agent")
                if prev_agent != agent:
                    st.session_state.cfg_db_connections[i] = [{}]

                row_data = {
                    "agent": agent,
                    "model": model,
                    "provider": provider,
                    "temperature": temp
                }

                # =============================
                # RAG
                # =============================
                if agent == "rag_agent":
                    st.markdown("##### RAG Configuration")

                    rcols = st.columns(2)

                    row_data["top_k"] = rcols[0].number_input(
                        "top_k",
                        min_value=1,
                        step=1,
                        # value=int(row.get("top_k", 3)),
                        key=f"edit_topk_{st.session_state.loaded_client_id}_{i}"
                    )

                    row_data["vector_db"] = rcols[1].selectbox(
                        "vector_db",
                        ["faiss", "chroma"],
                        index=["faiss", "chroma"].index(row.get("vector_db", "faiss")),
                        key=f"cfg_vdb_{i}"
                    )

                # =============================
                # SQL + NOSQL
                # =============================
                if agent in ["sql_agent", "nosql_agent"]:
                    st.markdown("##### Database Connections")

                    # ➕ ADD DB
                    if st.button("➕ Add DB", key=f"cfg_add_db_{i}"):
                        st.session_state.cfg_db_connections.setdefault(i, []).append({})
                        st.rerun()

                    st.session_state.cfg_db_connections.setdefault(i, [{}])
                    db_list = st.session_state.cfg_db_connections[i]

                    for j in range(len(db_list)):
                        db = db_list[j]

                        dcols = st.columns([1,1,1,1,1,1,0.5])

                        # db_type FIX
                        if agent == "sql_agent":
                            db_type = dcols[0].selectbox(
                                "db_type",
                                ["mysql","postgres","mssql","sqlite","mariadb"],
                                index=["mysql","postgres","mssql","sqlite","mariadb"].index(db.get("db_type","mysql")) if db.get("db_type") in ["mysql","postgres","mssql","sqlite","mariadb"] else 0,
                                key=f"cfg_db_{i}_{j}"
                            )
                        else:
                            db_type = dcols[0].selectbox(
                                "db_type",
                                ["mongo"],
                                index=0,
                                key=f"cfg_db_{i}_{j}"
                            )

                        host = dcols[1].text_input("host", value=db.get("host",""), key=f"cfg_h_{i}_{j}")
                        port = dcols[2].text_input("port", value=str(db.get("port","")), key=f"cfg_p_{i}_{j}")
                        user = dcols[3].text_input("username", value=db.get("username",""), key=f"cfg_u_{i}_{j}")
                        pwd = dcols[4].text_input("password", type="password", value=db.get("password",""), key=f"cfg_pw_{i}_{j}")
                        dbn = dcols[5].text_input("db_name", value=db.get("db_name",""), key=f"cfg_dn_{i}_{j}")

                        # REMOVE DB
                        with dcols[6]:
                            if len(db_list) > 1:
                                if st.button("✖", key=f"cfg_rm_db_{i}_{j}"):
                                    st.session_state.cfg_db_connections[i].pop(j)
                                    st.rerun()

                        st.session_state.cfg_db_connections[i][j] = {
                            "db_type": db_type,
                            "host": host,
                            "port": int(port) if port.isdigit() else None,
                            "username": user,
                            "password": pwd,
                            "db_name": dbn
                        }

                st.session_state.cfg_agent_rows[i].update(row_data)

            # =============================
            # UPDATE CONFIG
            # =============================
            if st.button("Update Config", key="cfg_update_btn"):
                updated_config = {}

                for i, row in enumerate(st.session_state.cfg_agent_rows):
                    agent = row["agent"]

                    base = {
                        "model_name": row["model"],
                        "provider": row["provider"],
                        "temperature": row["temperature"]
                    }

                    if agent == "rag_agent":
                        base["top_k"] = row["top_k"]
                        base["vector_db"] = row["vector_db"]

                    if agent in ["sql_agent", "nosql_agent"]:
                        dbs = st.session_state.cfg_db_connections.get(i, [])
                        base["database"] = {
                            f"connection{idx+1}": db for idx, db in enumerate(dbs)
                        }

                    updated_config[agent] = base

                cid = cmap[selected]

                res = requests.put(
                    f"{BASE_URL}/clients/update-client/{cid}",
                    json={"allowed_agents": updated_config},
                    headers=get_headers()
                )

                res.raise_for_status()
                st.success("Config updated successfully!")


# =====================================================
# MAIN
# =====================================================
def main():
    if not st.session_state.logged_in:
        login_ui()
        return

    user = st.session_state.user_data
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