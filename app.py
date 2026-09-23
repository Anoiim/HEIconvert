import streamlit as st

# Configuração global (chamada uma única vez, aqui)
st.set_page_config(
    page_title="HEIConvert",
    page_icon="🖼️",
    layout="wide",
)

# Define as páginas com os nomes exatos que aparecerão na sidebar
paginas = [
    st.Page(
        "paginas/heiconvert.py",
        title="HEIConvert",
        icon="🖼️",
        default=True,
    ),
    st.Page(
        "paginas/unir_pdfs.py",
        title="Unir PDFs",
        icon="🔗",
    ),
    st.Page(
        "paginas/download_massa.py",
        title="Download em Massa de Links de Planilha",
        icon="📥",
    ),
]

# Executa a página selecionada
nav = st.navigation(paginas)
nav.run()