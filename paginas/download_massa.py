import io
import os
import re
import zipfile
from urllib.parse import urlparse, unquote

import pandas as pd
import requests
import streamlit as st


# ============================================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================================

# st.set_page_config(
#     page_title="Download em Massa",
#     page_icon="📥",
#     layout="wide",
# )


# ============================================================
# CONFIGURAÇÕES
# ============================================================

TIMEOUT = 60

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    )
}

P = "dm_"

PREFERENCIAIS_NOME = [
    "nome", "name", "arquivo", "file",
    "documento", "document", "titulo", "title",
]

MAPA_CONTENT_TYPE = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/bmp": ".bmp",
    "image/tiff": ".tiff",
    "text/plain": ".txt",
    "text/csv": ".csv",
    "application/json": ".json",
    "application/xml": ".xml",
    "application/zip": ".zip",
    "application/x-rar-compressed": ".rar",
    "application/x-7z-compressed": ".7z",
    "application/gzip": ".gz",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.ms-excel": ".xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.ms-powerpoint": ".ppt",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
    "audio/ogg": ".ogg",
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/quicktime": ".mov",
}


# ============================================================
# ESTADO
# ============================================================

for chave in (
    "df_original", "df_filtrado", "resultados", "arquivos", "sheet_url"
):
    if f"{P}{chave}" not in st.session_state:
        st.session_state[f"{P}{chave}"] = (
            [] if chave == "arquivos"
            else "" if chave == "sheet_url"
            else None
        )


# ============================================================
# FUNÇÕES UTILITÁRIAS BÁSICAS
# ============================================================

def extrair_sheet_id(url: str):
    if not url:
        return None
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url)
    return match.group(1) if match else None


def baixar_planilha_google(url: str):
    sheet_id = extrair_sheet_id(url)
    if not sheet_id:
        raise ValueError(
            "URL inválida. Informe uma URL válida do Google Sheets."
        )

    csv_url = (
        f"https://docs.google.com/spreadsheets/d/"
        f"{sheet_id}/export?format=csv"
    )

    response = requests.get(csv_url, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()

    if not response.content:
        raise ValueError("A planilha retornou conteúdo vazio.")

    return pd.read_csv(io.BytesIO(response.content))


def limpar_valor(valor):
    if pd.isna(valor):
        return ""
    return str(valor).strip()


def url_valida(url: str) -> bool:
    if not url:
        return False
    return bool(re.match(r"^https?://", url, re.IGNORECASE))


def coluna_contem_links(series):
    valores = series.dropna().astype(str).str.strip()
    if len(valores) == 0:
        return False
    return valores.str.match(r"^https?://", case=False, na=False).sum() > 0


def encontrar_coluna_links(df):
    nomes_preferenciais = [
        "link", "links", "url", "urls",
        "arquivo", "arquivos", "download",
        "documento", "documentos",
    ]
    for coluna in df.columns:
        nome = str(coluna).strip().lower()
        if nome in nomes_preferenciais and coluna_contem_links(df[coluna]):
            return coluna
    for coluna in df.columns:
        if coluna_contem_links(df[coluna]):
            return coluna
    return None


def limpar_nome_arquivo(nome):
    nome = str(nome)
    nome = re.sub(r'[<>:"/\\|?*]', "_", nome)
    nome = nome.strip().strip(".")
    if not nome:
        nome = "arquivo"
    return nome


# ============================================================
# GOOGLE DRIVE
# ============================================================

def extrair_file_id_google_drive(url: str):
    """
    Extrai o FILE_ID de URLs do Google Drive.
    Retorna None se não for link do Drive.
    """
    if not url:
        return None

    # Formatos comuns:
    # https://drive.google.com/file/d/FILE_ID/view?usp=sharing
    # https://drive.google.com/open?id=FILE_ID
    # https://drive.google.com/uc?id=FILE_ID
    # https://docs.google.com/document/d/FILE_ID/...
    match = re.search(
        r"(?:drive|docs)\.google\.com/(?:file/d/|open\?id=|uc\?(?:export=\w+&)?id=|[^/]+/d/)([a-zA-Z0-9_-]{10,})",
        url,
    )
    if match:
        return match.group(1)

    # Formato apenas com ?id= ou &id=
    match = re.search(r"[?&]id=([a-zA-Z0-9_-]{10,})", url)
    if match:
        return match.group(1)

    return None


def normalizar_url_google_drive(url: str) -> str:
    """Converte qualquer URL do Google Drive para download direto."""
    file_id = extrair_file_id_google_drive(url)
    if not file_id:
        return url
    return f"https://drive.google.com/uc?export=download&id={file_id}"


def _extrair_campos_form(html: str):
    """
    Extrai os campos <input hidden> de um formulário HTML do Google Drive.
    Retorna (action_url, dict_de_campos).
    """
    action_match = re.search(
        r'<form[^>]+action="([^"]+)"',
        html,
        re.IGNORECASE,
    )
    action = action_match.group(1).replace("&amp;", "&") if action_match else None

    campos = {}
    for match in re.finditer(
        r'<input[^>]+name="([^"]+)"[^>]*value="([^"]*)"',
        html,
        re.IGNORECASE,
    ):
        campos[match.group(1)] = match.group(2)

    for match in re.finditer(
        r'<input[^>]+value="([^"]*)"[^>]*name="([^"]+)"',
        html,
        re.IGNORECASE,
    ):
        campos.setdefault(match.group(2), match.group(1))

    return action, campos


def baixar_do_google_drive(file_id: str):
    """
    Baixa um arquivo do Google Drive, tratando a página de confirmação
    para arquivos grandes ou contas que exigem confirmação.
    """
    session = requests.Session()
    url_base = "https://drive.google.com/uc"
    params = {"export": "download", "id": file_id}

    response = session.get(
        url_base,
        params=params,
        headers=HEADERS,
        timeout=TIMEOUT,
        allow_redirects=True,
    )
    response.raise_for_status()

    content_type = (
        response.headers.get("Content-Type", "")
        .split(";")[0]
        .strip()
        .lower()
    )

    if "text/html" not in content_type:
        return response

    # É a página de confirmação. Reenviar.

    # Estratégia 1: extrair <form> e reenviar os campos
    action, campos = _extrair_campos_form(response.text)
    if action and campos:
        campos.setdefault("id", file_id)
        campos.setdefault("export", "download")

        response = session.get(
            action,
            params=campos,
            headers=HEADERS,
            timeout=TIMEOUT,
            allow_redirects=True,
        )
        response.raise_for_status()

        content_type = (
            response.headers.get("Content-Type", "")
            .split(";")[0]
            .strip()
            .lower()
        )
        if "text/html" not in content_type:
            return response

    # Estratégia 2: token confirm=...
    match = re.search(r"confirm=([0-9A-Za-z_-]+)", response.text)
    if match:
        params["confirm"] = match.group(1)
        response = session.get(
            url_base,
            params=params,
            headers=HEADERS,
            timeout=TIMEOUT,
            allow_redirects=True,
        )
        response.raise_for_status()

        content_type = (
            response.headers.get("Content-Type", "")
            .split(";")[0]
            .strip()
            .lower()
        )
        if "text/html" not in content_type:
            return response

    # Estratégia 3: uuid + confirm=t
    match = re.search(r'name="uuid"\s+value="([^"]+)"', response.text)
    if match:
        params["confirm"] = "t"
        params["uuid"] = match.group(1)
        response = session.get(
            url_base,
            params=params,
            headers=HEADERS,
            timeout=TIMEOUT,
            allow_redirects=True,
        )
        response.raise_for_status()

    return response


# ============================================================
# DETECÇÃO DE EXTENSÃO
# ============================================================

def extrair_nome_do_content_disposition(response):
    cd = response.headers.get("Content-Disposition", "")
    if not cd:
        return None

    match = re.search(r"filename\*\s*=\s*([^;]+)", cd, re.IGNORECASE)
    if match:
        valor = match.group(1).strip().strip('"').strip("'")
        if "''" in valor:
            valor = valor.split("''", 1)[1]
        try:
            return unquote(valor)
        except Exception:
            return valor

    for padrao in (
        r'filename\s*=\s*"([^"]+)"',
        r"filename\s*=\s*'([^']+)'",
        r"filename\s*=\s*([^;]+)",
    ):
        match = re.search(padrao, cd, re.IGNORECASE)
        if match:
            return match.group(1).strip().strip('"').strip("'")

    return None


def detectar_extensao_por_magic_bytes(conteudo: bytes):
    if not conteudo or len(conteudo) < 4:
        return None

    if conteudo[:4] == b"%PDF":
        return ".pdf"
    if conteudo[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if conteudo[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if conteudo[:6] in (b"GIF87a", b"GIF89a"):
        return ".gif"
    if conteudo[:2] == b"BM":
        return ".bmp"
    if conteudo[:4] in (b"II*\x00", b"MM\x00*"):
        return ".tiff"

    if conteudo[:4] == b"RIFF" and len(conteudo) >= 12:
        sub = conteudo[8:12]
        if sub == b"WEBP":
            return ".webp"
        if sub == b"WAVE":
            return ".wav"
        if sub == b"AVI ":
            return ".avi"

    if conteudo[:4] == b"Rar!":
        return ".rar"
    if conteudo[:6] == b"7z\xbc\xaf\x27\x1c":
        return ".7z"
    if conteudo[:2] == b"\x1f\x8b":
        return ".gz"

    if conteudo[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return None

    if conteudo[:4] == b"PK\x03\x04":
        try:
            with zipfile.ZipFile(io.BytesIO(conteudo)) as zf:
                nomes = zf.namelist()
                if any(n.startswith("word/") for n in nomes):
                    return ".docx"
                if any(n.startswith("xl/") for n in nomes):
                    return ".xlsx"
                if any(n.startswith("ppt/") for n in nomes):
                    return ".pptx"
                if "mimetype" in nomes:
                    try:
                        mime = zf.read("mimetype").decode("utf-8", errors="ignore")
                        if "opendocument.text" in mime:
                            return ".odt"
                        if "opendocument.spreadsheet" in mime:
                            return ".ods"
                        if "opendocument.presentation" in mime:
                            return ".odp"
                    except Exception:
                        pass
        except Exception:
            pass
        return ".zip"

    if conteudo[:3] == b"ID3" or conteudo[:2] in (
        b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"
    ):
        return ".mp3"

    if len(conteudo) >= 12 and conteudo[4:8] == b"ftyp":
        return ".mp4"

    return None


def descobrir_extensao(response, url, conteudo):
    nome_cd = extrair_nome_do_content_disposition(response)
    if nome_cd:
        ext = os.path.splitext(nome_cd)[1]
        if ext:
            return ext.lower()

    content_type = (
        response.headers.get("Content-Type", "")
        .split(";")[0]
        .strip()
        .lower()
    )
    if content_type in MAPA_CONTENT_TYPE:
        return MAPA_CONTENT_TYPE[content_type]

    path = urlparse(url).path
    ext = os.path.splitext(path)[1]
    if ext and 1 < len(ext) <= 6:
        return ext.lower()

    ext = detectar_extensao_por_magic_bytes(conteudo)
    if ext:
        return ext

    return ".bin"


def obter_nome_base(row, url, indice):
    for coluna in row.index:
        nc = str(coluna).strip().lower()
        if nc in PREFERENCIAIS_NOME:
            valor = limpar_valor(row[coluna])
            if valor:
                base, ext = os.path.splitext(valor)
                return base if ext else valor

    path = urlparse(url).path
    nome = os.path.basename(path)
    if nome:
        base, ext = os.path.splitext(nome)
        return base if ext else nome

    return f"arquivo_{indice}"


def _parece_html_valido(conteudo: bytes) -> bool:
    if not conteudo:
        return False
    head = conteudo[:512].lower()
    return (
        b"<html" in head
        or b"<!doctype html" in head
        or b"<head" in head
    )


# ============================================================
# DOWNLOAD DE ARQUIVO
# ============================================================

def baixar_arquivo(url, row, indice, tentativas=2):
    if not url_valida(url):
        raise ValueError(f"URL inválida (apenas http/https): {url}")

    ultimo_erro = None

    for tentativa in range(1, tentativas + 1):
        try:
            # Google Drive tem caminho especial
            file_id = extrair_file_id_google_drive(url)
            if file_id:
                response = baixar_do_google_drive(file_id)
            else:
                response = requests.get(
                    url,
                    headers=HEADERS,
                    timeout=TIMEOUT,
                    allow_redirects=True,
                )
                response.raise_for_status()

            conteudo = response.content

            content_type = (
                response.headers.get("Content-Type", "")
                .split(";")[0]
                .strip()
                .lower()
            )

            # Se veio HTML, provavelmente é página de erro/preview
            if content_type == "text/html" and _parece_html_valido(conteudo):
                raise RuntimeError(
                    "O servidor retornou uma página HTML em vez do arquivo. "
                    "Verifique se o link é de download direto e se o arquivo "
                    "está público (compartilhado com 'qualquer pessoa com o link')."
                )

            nome_base = obter_nome_base(row, url, indice)
            nome_base = limpar_nome_arquivo(nome_base)

            base2, ext2 = os.path.splitext(nome_base)
            if ext2 and 1 < len(ext2) <= 6:
                return nome_base, conteudo

            nome_cd = extrair_nome_do_content_disposition(response)
            ext_final = None

            if nome_cd:
                _, ext_cd = os.path.splitext(nome_cd)
                if ext_cd and 1 < len(ext_cd) <= 6:
                    ext_final = ext_cd.lower()

            if not ext_final:
                ext_final = descobrir_extensao(response, url, conteudo)

            return nome_base + ext_final, conteudo

        except Exception as e:
            ultimo_erro = e
            if tentativa < tentativas:
                continue

    raise ultimo_erro


def gerar_zip(arquivos):
    buffer = io.BytesIO()
    nomes_usados = set()

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for nome, conteudo in arquivos:
            nome_original = nome
            contador = 1

            while nome.lower() in nomes_usados:
                base, extensao = os.path.splitext(nome_original)
                nome = f"{base}_{contador}{extensao}"
                contador += 1

            nomes_usados.add(nome.lower())
            zip_file.writestr(nome, conteudo)

    buffer.seek(0)
    return buffer


# ============================================================
# CABEÇALHO
# ============================================================

st.title("📥 Download de arquivos em massa")

st.markdown(
    """
    Carregue uma planilha do **Google Sheets**, filtre os registros
    desejados e baixe os arquivos selecionados em um único ZIP.
    """
)

st.info(
    "📊 **Compatível apenas com planilhas do Google Sheets.** "
    "Outros formatos (Excel, CSV local, OneDrive, etc.) não são suportados "
    "nesta página."
)

with st.expander("Configuração necessária da planilha", expanded=False):
    st.markdown(
        """
                Para que o app consiga ler a planilha, ela **precisa estar
                compartilhada publicamente**. Siga os passos:
    
                ### 🔓 Como compartilhar a planilha
    
                1. Abra a planilha no Google Sheets
                2. Clique em **Compartilhar** (canto superior direito)
                3. Em **Acesso geral**, altere de *"Restrito"* para
                   **"Qualquer pessoa com o link"**
                4. Defina a permissão como **Leitor** (suficiente)
                5. Clique em **Concluir**
                6. Copie o link da barra de endereços e cole no campo abaixo
        """)

    # ============================================================
    # URL DA PLANILHA
    # ============================================================

    st.subheader("1️⃣ Planilha")

    url_planilha = st.text_input(
        "URL do Google Sheets",
        value=st.session_state[f"{P}sheet_url"],
        placeholder="https://docs.google.com/spreadsheets/d/...",
    )

    col_carregar, col_limpar = st.columns([1, 1])

    with col_carregar:
        carregar = st.button(
            "🔄 Carregar planilha",
            type="primary",
            use_container_width=True,
        )

    with col_limpar:
        limpar = st.button("🗑️ Limpar", use_container_width=True)


    if limpar:
        st.session_state[f"{P}df_original"] = None
        st.session_state[f"{P}df_filtrado"] = None
        st.session_state[f"{P}resultados"] = None
        st.session_state[f"{P}arquivos"] = []
        st.session_state[f"{P}sheet_url"] = ""

        for chave in list(st.session_state.keys()):
            if chave.startswith(f"{P}arquivo_") or chave == f"{P}selecionar_todos":
                del st.session_state[chave]

        st.rerun()


    if carregar:
        try:
            with st.spinner("Carregando dados do Google Sheets..."):
                df = baixar_planilha_google(url_planilha)

            st.session_state[f"{P}df_original"] = df
            st.session_state[f"{P}df_filtrado"] = df.copy()
            st.session_state[f"{P}resultados"] = None
            st.session_state[f"{P}arquivos"] = []
            st.session_state[f"{P}sheet_url"] = url_planilha

            st.success(f"Planilha carregada: {len(df)} registros encontrados.")

        except Exception as erro:
            st.error(f"❌ Não foi possível carregar a planilha: {erro}")


    # ============================================================
    # PROCESSAMENTO
    # ============================================================

    if st.session_state[f"{P}df_original"] is not None:

        df = st.session_state[f"{P}df_original"].copy()

        st.divider()
        st.subheader("2️⃣ Configuração")

        coluna_detectada = encontrar_coluna_links(df)
        colunas = list(df.columns)

        indice_padrao = 0
        if coluna_detectada in colunas:
            indice_padrao = colunas.index(coluna_detectada)

        coluna_links = st.selectbox(
            "🔗 Coluna que contém os links",
            colunas,
            index=indice_padrao,
        )

        st.subheader("3️⃣ Filtros")
        st.caption(
            "Os filtros são aplicados somente no Streamlit. "
            "Você pode combinar vários filtros."
        )

        colunas_filtro = [c for c in df.columns if c != coluna_links]
        filtros = {}
        colunas_alta_cardinalidade = set()

        if not colunas_filtro:
            st.info("Não existem outras colunas disponíveis para filtro.")
        else:
            for inicio in range(0, len(colunas_filtro), 3):
                grupo = colunas_filtro[inicio:inicio + 3]
                colunas_ui = st.columns(len(grupo))

                for coluna, coluna_ui in zip(grupo, colunas_ui):
                    with coluna_ui:
                        valores = (
                            df[coluna].dropna().astype(str).str.strip()
                        )
                        valores = sorted(valores.unique())

                        if len(valores) <= 100:
                            opcoes = ["Todos"] + valores
                            selecionado = st.selectbox(
                                str(coluna),
                                opcoes,
                                key=f"{P}filtro_{coluna}",
                            )
                            if selecionado != "Todos":
                                filtros[coluna] = selecionado
                        else:
                            colunas_alta_cardinalidade.add(coluna)
                            texto = st.text_input(
                                f"{coluna} contém",
                                key=f"{P}texto_{coluna}",
                            )
                            if texto.strip():
                                filtros[coluna] = texto.strip()

        df_filtrado = df.copy()

        for coluna, valor in filtros.items():
            valores_coluna = df_filtrado[coluna].fillna("").astype(str)

            if coluna in colunas_alta_cardinalidade:
                df_filtrado = df_filtrado[
                    valores_coluna.str.contains(valor, case=False, na=False)
                ]
            else:
                df_filtrado = df_filtrado[
                    valores_coluna.str.strip() == valor
                ]

        st.session_state[f"{P}df_filtrado"] = df_filtrado.copy()

        st.divider()
        st.subheader("4️⃣ Resultado dos filtros")

        links_validos = (
            df_filtrado[coluna_links]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.match(r"^https?://", case=False, na=False)
        )

        col1, col2, col3 = st.columns(3)
        col1.metric("📊 Total da planilha", len(df))
        col2.metric("🔎 Após filtros", len(df_filtrado))
        col3.metric("🔗 Links válidos", int(links_validos.sum()))

        st.subheader("5️⃣ Registros")

        if len(df_filtrado) == 0:
            st.warning("Nenhum registro corresponde aos filtros.")
        else:
            st.dataframe(df_filtrado, use_container_width=True, height=350)

            st.subheader("6️⃣ Selecionar arquivos")
            st.caption(
                "Por padrão, todos os registros filtrados "
                "com links válidos serão baixados."
            )

            df_download = df_filtrado[links_validos].copy()

            if len(df_download) > 0:
                indices_disponiveis = df_download.index.tolist()

                for indice in indices_disponiveis:
                    chave = f"{P}arquivo_{indice}"
                    if chave not in st.session_state:
                        st.session_state[chave] = True

                st.session_state[f"{P}_indices_arquivo"] = indices_disponiveis

                def _toggle_todos():
                    valor = st.session_state.get(f"{P}selecionar_todos", True)
                    for idx in st.session_state.get(f"{P}_indices_arquivo", []):
                        st.session_state[f"{P}arquivo_{idx}"] = valor

                st.checkbox(
                    "☑️ Selecionar todos",
                    value=True,
                    key=f"{P}selecionar_todos",
                    on_change=_toggle_todos,
                )

                indices_selecionados = []

                for indice in indices_disponiveis:
                    row = df_download.loc[indice]

                    nome_exibicao = ""
                    for coluna_nome in [
                        "nome", "name", "arquivo", "file",
                        "documento", "titulo", "title",
                    ]:
                        coluna_real = next(
                            (c for c in row.index
                             if str(c).lower() == coluna_nome),
                            None,
                        )
                        if coluna_real:
                            valor = limpar_valor(row[coluna_real])
                            if valor:
                                nome_exibicao = valor
                                break

                    if not nome_exibicao:
                        nome_exibicao = f"Registro {indice + 1}"

                    url = limpar_valor(row[coluna_links])
                    label = f"{nome_exibicao} — {url}"

                    if st.checkbox(label, key=f"{P}arquivo_{indice}"):
                        indices_selecionados.append(indice)

                st.info(
                    f"📦 {len(indices_selecionados)} arquivo(s) selecionado(s)"
                )

                if st.button(
                    "📥 Baixar arquivos selecionados",
                    type="primary",
                    use_container_width=True,
                ):
                    arquivos = []
                    resultados = []
                    progresso = st.progress(0)
                    status = st.empty()
                    total = len(indices_selecionados)

                    for posicao, indice in enumerate(indices_selecionados, start=1):
                        row = df_download.loc[indice]
                        url = limpar_valor(row[coluna_links])
                        nome_base = obter_nome_base(row, url, indice + 1)

                        status.write(
                            f"📥 Baixando {posicao}/{total}: {nome_base}"
                        )

                        try:
                            nome, conteudo = baixar_arquivo(url, row, indice + 1)
                            arquivos.append((nome, conteudo))

                            resultados.append({
                                "Linha": indice + 2,
                                "Arquivo": nome,
                                "URL": url,
                                "Status": "Sucesso",
                                "Erro": "",
                            })
                        except Exception as erro:
                            resultados.append({
                                "Linha": indice + 2,
                                "Arquivo": nome_base,
                                "URL": url,
                                "Status": "Erro",
                                "Erro": str(erro),
                            })

                        progresso.progress(posicao / total)

                    status.success("✅ Download finalizado!")

                    st.session_state[f"{P}arquivos"] = arquivos
                    st.session_state[f"{P}resultados"] = pd.DataFrame(resultados)

            else:
                st.warning("Nenhum link válido encontrado após os filtros.")


    # ============================================================
    # RESULTADOS
    # ============================================================

    if st.session_state[f"{P}resultados"] is not None:

        st.divider()
        st.subheader("7️⃣ Resultado dos downloads")

        resultados = st.session_state[f"{P}resultados"]
        total = len(resultados)
        sucesso = len(resultados[resultados["Status"] == "Sucesso"])
        erros = len(resultados[resultados["Status"] == "Erro"])

        col1, col2, col3 = st.columns(3)
        col1.metric("Total processado", total)
        col2.metric("✅ Sucesso", sucesso)
        col3.metric("❌ Erros", erros)

        st.dataframe(resultados, use_container_width=True, height=300)

        arquivos = st.session_state[f"{P}arquivos"]

        if arquivos:
            st.subheader("8️⃣ Arquivos")
            zip_buffer = gerar_zip(arquivos)

            st.download_button(
                label="📦 Baixar todos em ZIP",
                data=zip_buffer,
                file_name="downloads.zip",
                mime="application/zip",
                type="primary",
                use_container_width=True,
            )

        csv_resultado = resultados.to_csv(index=False).encode("utf-8-sig")

        st.download_button(
            label="📄 Baixar relatório CSV",
            data=csv_resultado,
            file_name="relatorio_downloads.csv",
            mime="text/csv",
            use_container_width=True,
        )


    # ============================================================
    # RODAPÉ
    # ============================================================

    st.divider()
    st.caption("Download em Massa • Python + Streamlit")