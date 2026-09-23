import streamlit as st
import io

# Tentar importar PyMuPDF (fitz)
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

# Configuração da página
# st.set_page_config(
#     page_title="Unir PDFs - HEIConvert",
#     page_icon="🔗",
#     layout="wide"
# )

# --- Limites ---
MAX_PAGES = 500
MAX_TOTAL_SIZE_MB = 500

# --- Verificação de dependência ---
if not PYMUPDF_AVAILABLE:
    st.error("⚠️ PyMuPDF não está instalado. Instale com: `pip install pymupdf`")
    st.stop()

# --- Título ---
st.title("🔗 Unir PDFs")
st.markdown(f"""
Combine vários arquivos PDF em um único documento.

**Limites:**
- Até **{MAX_PAGES} páginas** no total
- Até **{MAX_TOTAL_SIZE_MB} MB** de tamanho total
""")

# --- Sidebar ---
with st.sidebar:
    st.header("ℹ️ Como usar")
    st.markdown(f"""
    1. Faça upload de **2 ou mais PDFs**
    2. Ajuste a **ordem** (botões ⬆️ / ⬇️)
    3. Escolha se quer **preservar campos/assinaturas**
    4. Clique em **Unir PDFs**
    5. Baixe o resultado

    **Sobre assinaturas digitais:**
    - A união **sempre invalida** assinaturas digitais
    - A opção de "achatar" preserva só a **aparência visual**
    - A validade criptográfica é perdida em qualquer caso
    """)
    st.divider()
    st.caption("🔧 HEIConvert • Módulo de união de PDFs")


# --- Upload ---
uploaded_pdfs = st.file_uploader(
    "Selecione os arquivos PDF para unir",
    type=['pdf'],
    accept_multiple_files=True,
    key="merge_pdfs_uploader"
)

# --- Inicializa ordem na sessão ---
if 'pdf_merge_order' not in st.session_state:
    st.session_state.pdf_merge_order = []


if uploaded_pdfs:
    # Validação de nomes duplicados
    names = [f.name for f in uploaded_pdfs]
    if len(names) != len(set(names)):
        st.error("⚠️ Existem arquivos com o mesmo nome. Renomeie-os antes de enviar.")
        st.stop()

    file_map = {f.name: f for f in uploaded_pdfs}

    # Sincroniza ordem
    current_order = [n for n in st.session_state.pdf_merge_order if n in file_map]
    for n in names:
        if n not in current_order:
            current_order.append(n)
    st.session_state.pdf_merge_order = current_order

    # --- Analisa cada PDF ---
    pdf_info = {}
    total_pages = 0
    total_size_bytes = 0
    erros = []

    for name in st.session_state.pdf_merge_order:
        pdf_file = file_map[name]
        try:
            pdf_file.seek(0)
            pdf_bytes = pdf_file.read()
            pdf_file.seek(0)

            file_size = len(pdf_bytes)
            total_size_bytes += file_size

            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            if doc.needs_pass:
                erros.append(f"🔒 **{name}** está protegido por senha.")
                doc.close()
                continue

            num_pages = doc.page_count

            # Detecta se tem widgets/annots (para avisar o usuário)
            tem_widgets = False
            tem_annots = False
            try:
                for page in doc:
                    if page.widgets() and len(list(page.widgets())) > 0:
                        tem_widgets = True
                    if page.annots() and len(list(page.annots())) > 0:
                        tem_annots = True
                    if tem_widgets and tem_annots:
                        break
            except Exception:
                pass

            total_pages += num_pages
            pdf_info[name] = {
                'pages': num_pages,
                'file': pdf_file,
                'size_mb': file_size / (1024 * 1024),
                'tem_widgets': tem_widgets,
                'tem_annots': tem_annots,
            }
            doc.close()
        except Exception as e:
            erros.append(f"❌ Erro ao ler **{name}**: {e}")

    for err in erros:
        st.warning(err)

    total_size_mb = total_size_bytes / (1024 * 1024)

    # --- Resumo ---
    st.divider()
    col_a, col_b, col_c, col_d = st.columns(4)
    with col_a:
        st.metric("📄 Arquivos válidos", len(pdf_info))
    with col_b:
        st.metric("📑 Total de páginas", total_pages)
    with col_c:
        restantes = MAX_PAGES - total_pages
        st.metric("✅ Páginas restantes", max(restantes, 0))
    with col_d:
        st.metric("💾 Tamanho total", f"{total_size_mb:.1f} MB")

    # --- Lista com ordem ajustável ---
    if pdf_info:
        st.subheader("📋 Ordem dos arquivos")
        st.caption("Use os botões ⬆️ e ⬇️ para reorganizar. A ordem acima será a ordem final.")

        for idx, name in enumerate(st.session_state.pdf_merge_order):
            if name not in pdf_info:
                continue

            info = pdf_info[name]
            c1, c2, c3, c4, c5, c6 = st.columns([1, 6, 2, 2, 1, 1])

            with c1:
                st.markdown(f"**{idx + 1}.**")
            with c2:
                marcadores = ""
                if info['tem_widgets']:
                    marcadores += " 📝"
                if info['tem_annots']:
                    marcadores += " 📌"
                st.markdown(f"`{name}`{marcadores}")
            with c3:
                st.markdown(f"{info['pages']} página(s)")
            with c4:
                st.markdown(f"{info['size_mb']:.2f} MB")
            with c5:
                if st.button("⬆️", key=f"up_{name}", disabled=(idx == 0),
                             help="Mover para cima"):
                    order = st.session_state.pdf_merge_order
                    order[idx], order[idx - 1] = order[idx - 1], order[idx]
                    st.rerun()
            with c6:
                if st.button("⬇️", key=f"down_{name}",
                             disabled=(idx == len(st.session_state.pdf_merge_order) - 1),
                             help="Mover para baixo"):
                    order = st.session_state.pdf_merge_order
                    order[idx], order[idx + 1] = order[idx + 1], order[idx]
                    st.rerun()

        # Legenda dos marcadores
        st.caption("📝 = tem campos de formulário • 📌 = tem anotações/assinaturas")

    # --- Opções avançadas ---
    st.divider()
    st.subheader("⚙️ Opções avançadas")

    # Detecta se algum arquivo tem widgets/annots
    algum_tem_campos = any(
        info.get('tem_widgets') or info.get('tem_annots')
        for info in pdf_info.values()
    )

    if algum_tem_campos:
        st.info(
            "🔍 Foram detectados arquivos com **campos de formulário** "
            "e/ou **anotações** (que incluem assinaturas). Escolha como "
            "deseja tratá-los na união."
        )

    achatar = st.checkbox(
        "Preservar a aparência visual de campos e assinaturas (achatar)",
        value=algum_tem_campos,
        help=(
            "Ao marcar, o PyMuPDF converte campos de formulário e anotações "
            "em conteúdo estático da página, preservando a APARÊNCIA visual "
            "das assinaturas.\n\n"
            "⚠️ Importante: a VALIDADE da assinatura digital é perdida em "
            "qualquer cenário de união, porque o documento original é alterado. "
            "Esta opção só preserva a imagem da assinatura."
        )
    )

    if achatar:
        st.warning(
            "⚠️ **Aviso jurídico:** A assinatura digital será visualmente "
            "preservada, mas **perderá sua validade criptográfica**. "
            "O PDF unificado não será reconhecido como assinado por "
            "verificadores de assinatura."
        )

    # --- Verificação de limites ---
    st.divider()

    if total_pages == 0:
        st.error("Nenhum PDF válido para unir.")
    elif total_pages > MAX_PAGES:
        st.error(
            f"❌ O total de **{total_pages} páginas** excede o limite de "
            f"**{MAX_PAGES} páginas**."
        )
    elif total_size_mb > MAX_TOTAL_SIZE_MB:
        st.error(
            f"❌ O tamanho total (**{total_size_mb:.1f} MB**) excede o limite de "
            f"**{MAX_TOTAL_SIZE_MB} MB**."
        )
    elif len(pdf_info) < 2:
        st.warning("Adicione pelo menos **2 PDFs** para unir.")
    else:
        st.success(
            f"✅ Pronto para unir **{total_pages} páginas** "
            f"de {len(pdf_info)} arquivo(s) ({total_size_mb:.1f} MB)."
        )

        if total_pages > 300:
            st.info(
                "ℹ️ Com mais de 300 páginas, o processo pode levar "
                "alguns segundos. Aguarde até o download aparecer."
            )

        # --- Botão de união ---
        if st.button("🔗 Unir PDFs", type="primary", use_container_width=True):
            progress = st.progress(0)
            status = st.empty()

            try:
                merged_doc = fitz.open()

                total_files = len([n for n in st.session_state.pdf_merge_order if n in pdf_info])
                processed = 0
                erros_uniao = []
                avisos_bake = []

                for name in st.session_state.pdf_merge_order:
                    if name not in pdf_info:
                        continue

                    processed += 1
                    status.info(f"Processando **{name}** ({processed}/{total_files})...")
                    info = pdf_info[name]

                    info['file'].seek(0)
                    pdf_bytes = info['file'].read()
                    info['file'].seek(0)

                    try:
                        src_doc = fitz.open(stream=pdf_bytes, filetype="pdf")

                        # ==========================================
                        # Achatar campos e anotações (opcional)
                        # ==========================================
                        if achatar:
                            try:
                                src_doc.bake(
                                    annots=True,
                                    widgets=True,
                                )
                            except Exception as e_bake:
                                avisos_bake.append(
                                    f"⚠️ `{name}`: não foi possível achatar "
                                    f"campos/assinaturas ({e_bake}). "
                                    f"O arquivo será unido sem eles."
                                )

                        # ==========================================
                        # União direta (rápida e preserva estrutura)
                        # ==========================================
                        merged_doc.insert_pdf(
                            src_doc,
                            widgets=False,
                            annots=False,
                            links=False,
                        )
                        src_doc.close()

                    except Exception as e:
                        # ==========================================
                        # Fallback: cópia página a página
                        # ==========================================
                        erros_uniao.append(
                            f"⚠️ `{name}`: união direta falhou ({e}). "
                            f"Tentando método alternativo..."
                        )
                        try:
                            src_doc = fitz.open(stream=pdf_bytes, filetype="pdf")

                            if achatar:
                                try:
                                    src_doc.bake(annots=True, widgets=True)
                                except Exception:
                                    pass

                            for page_num in range(src_doc.page_count):
                                src_page = src_doc.load_page(page_num)
                                new_page = merged_doc.new_page(
                                    width=src_page.rect.width,
                                    height=src_page.rect.height,
                                )
                                new_page.show_pdf_page(
                                    new_page.rect,
                                    src_doc,
                                    page_num,
                                )
                            src_doc.close()
                        except Exception as e2:
                            erros_uniao.append(
                                f"❌ `{name}`: falha definitiva ({e2}). "
                                f"Arquivo ignorado."
                            )

                    progress.progress(processed / total_files)

                for msg in avisos_bake:
                    st.warning(msg)
                for msg in erros_uniao:
                    st.warning(msg)

                status.info("💾 Salvando PDF unificado...")

                # ⚠️ Ler page_count ANTES de fechar
                final_pages = merged_doc.page_count

                output_bytes = io.BytesIO()
                merged_doc.save(output_bytes, deflate=True, garbage=4)
                merged_doc.close()
                output_bytes.seek(0)

                final_size_mb = output_bytes.getbuffer().nbytes / (1024 * 1024)

                progress.progress(100)
                status.success(
                    f"✅ PDF unificado com sucesso! "
                    f"**{final_pages} páginas** • **{final_size_mb:.1f} MB**."
                )

                st.download_button(
                    label=(
                        f"📥 Baixar PDF unificado "
                        f"({final_pages} páginas, {final_size_mb:.1f} MB)"
                    ),
                    data=output_bytes,
                    file_name="pdf_unificado.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )

            except MemoryError:
                progress.empty()
                status.empty()
                st.error(
                    "❌ Memória insuficiente para unir esses arquivos. "
                    "Tente dividir em lotes menores."
                )
            except Exception as e:
                progress.empty()
                status.empty()
                st.error(f"Erro ao unir PDFs: {e}")

else:
    st.info(f"""
    👆 **Como usar esta página:**
    1. Faça upload de dois ou mais arquivos PDF
    2. Confira o total de páginas (limite: {MAX_PAGES})
    3. Reorganize a ordem se necessário
    4. Clique em **Unir PDFs** e baixe o resultado
    """)

    with st.expander("💡 Dicas e limitações"):
        st.markdown(f"""
        - **Limite de {MAX_PAGES} páginas** por vez, para evitar consumo excessivo de memória.
        - **Limite de {MAX_TOTAL_SIZE_MB} MB** de tamanho total.
        - Se precisar unir mais páginas, faça em lotes de até {MAX_PAGES}.
        - PDFs protegidos por senha não são suportados nesta versão.
        - Arquivos com o **mesmo nome** precisam ser renomeados antes do upload.
        - A ordem dos arquivos pode ser ajustada com os botões ⬆️/⬇️.

        **Sobre campos e assinaturas:**
        - Na união, **campos de formulário** e **anotações** são removidos por padrão.
        - Se quiser **preservar a aparência visual** das assinaturas, marque a opção
          "Achatar" nas opções avançadas.
        - ⚠️ Em qualquer cenário, a **validade jurídica** da assinatura digital
          é perdida ao unir PDFs, pois o documento original é alterado.
        """)