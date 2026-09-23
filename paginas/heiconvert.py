import streamlit as st
import os
import io
import zipfile
from PIL import Image, UnidentifiedImageError
from pillow_heif import register_heif_opener
import img2pdf

# Tentar importar PyMuPDF (fitz) para conversão de PDF
try:
    import fitz  # PyMuPDF

    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    st.warning("PyMuPDF não está instalado. A conversão de PDF para imagem será desabilitada.")

# Registrar o opener para HEIC/HEIF
register_heif_opener()

# Configuração da página
#st.set_page_config(
   # page_title="HEIconvert",
  #  page_icon="🖼️",
 #   layout="wide"
#)

# --- Valores padrão para evitar NameError ---
output_format = "JPG"  # padrão
quality = 85  # padrão para JPG
dpi_pdf = 150  # padrão para renderização de PDF

# Título e descrição
st.title("🖼️ HEIConvert")
st.markdown("""
Conversor de imagens HEIC/HEIF para formatos JPG, PNG ou PDF.
Agora também suporta **conversão de PDF para JPG/PNG**!
""")

# Sidebar com informações
with st.sidebar:
    st.header("ℹ️ Informações")
    st.markdown("""
    **Formatos suportados para entrada:**
    - HEIC/HEIF (.heic, .heif)
    - JPEG/JPG (.jpg, .jpeg)
    - PNG (.png)
    - WebP (.webp)
    - BMP (.bmp)
    - TIFF (.tiff, .tif)
    - PDF (.pdf) → **convertido para imagens**

    **Formatos de saída:**
    - JPG
    - PNG
    - PDF (para uma ou múltiplas imagens)

    **Limitações:**
    - Tamanho máximo: 200 MB
    - Para PDF: múltiplas imagens serão combinadas em um único arquivo
    - Conversão de PDF → JPG/PNG gera uma imagem por página
    """)

    st.divider()
    st.markdown("### Dicas")
    st.markdown("""
    1. Para converter PDF para imagens, escolha JPG ou PNG como saída.
    2. Cada página do PDF se tornará um arquivo de imagem separado.
    3. Ajuste a qualidade JPG conforme necessário.
    4. Imagens HEIC mantêm transparência ao converter para PNG.
    """)


# Função para converter imagem
def convert_image(image_file, output_format, quality=95, dpi=None):
    try:
        # Abrir a imagem
        image = Image.open(image_file)

        # Converter para RGB se necessário (para JPG e PDF)
        if output_format in ['JPG', 'PDF'] and image.mode in ('RGBA', 'LA', 'P'):
            # Criar fundo branco para imagens com transparência
            bg = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('RGBA')
            bg.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
            image = bg

        # Salvar em um buffer de bytes
        img_byte_arr = io.BytesIO()

        if output_format == 'JPG':
            image.save(img_byte_arr, format='JPEG', quality=quality, optimize=True)
            mime_type = 'image/jpeg'
            file_extension = 'jpg'
        elif output_format == 'PNG':
            image.save(img_byte_arr, format='PNG', optimize=True)
            mime_type = 'image/png'
            file_extension = 'png'
        elif output_format == 'PDF':
            # Para PDF, vamos usar img2pdf para melhor controle
            img_byte_arr = io.BytesIO()
            if dpi:
                # Converter imagem para bytes no formato PNG para manter qualidade
                img_bytes = io.BytesIO()
                image.save(img_bytes, format='PNG')
                img_bytes.seek(0)
                # Criar PDF com img2pdf
                pdf_bytes = img2pdf.convert(img_bytes)
                img_byte_arr.write(pdf_bytes)
            else:
                # Metodo simples com Pillow
                image.save(img_byte_arr, format='PDF')
            mime_type = 'application/pdf'
            file_extension = 'pdf'

        img_byte_arr.seek(0)
        return img_byte_arr, mime_type, file_extension, image.size

    except UnidentifiedImageError:
        st.error(f"Erro: Não foi possível identificar a imagem. O arquivo pode estar corrompido.")
        return None, None, None, None
    except Exception as e:
        st.error(f"Erro ao converter imagem: {str(e)}")
        return None, None, None, None


# Função para converter PDF para imagens (cada página vira uma imagem)
def convert_pdf_to_images(pdf_file, output_format, quality=95, dpi=150):
    if not PYMUPDF_AVAILABLE:
        st.error("PyMuPDF não está disponível. Não é possível converter PDF para imagem.")
        return []

    try:
        # Ler o conteúdo do PDF
        pdf_bytes = pdf_file.read()
        pdf_file.seek(0)  # reset para possíveis usos posteriores

        # Abrir o documento com fitz
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        images_data = []

        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            # Renderizar página para imagem (pixmap)
            zoom = dpi / 72  # 72 dpi é o padrão do PDF
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)

            # Converter pixmap para bytes PIL
            img_data = pix.tobytes("ppm")  # PPM é suportado pelo PIL
            img = Image.open(io.BytesIO(img_data))

            # Converter para RGB se necessário (para JPG)
            if output_format == 'JPG' and img.mode != 'RGB':
                img = img.convert('RGB')

            # Salvar em buffer
            img_byte_arr = io.BytesIO()
            if output_format == 'JPG':
                img.save(img_byte_arr, format='JPEG', quality=quality, optimize=True)
                mime_type = 'image/jpeg'
                ext = 'jpg'
            else:  # PNG
                img.save(img_byte_arr, format='PNG', optimize=True)
                mime_type = 'image/png'
                ext = 'png'

            img_byte_arr.seek(0)
            # Nome do arquivo: nome_original_paginaX.ext
            base_name = os.path.splitext(pdf_file.name)[0]
            output_name = f"{base_name}_pagina{page_num + 1}.{ext}"

            images_data.append({
                'data': img_byte_arr,
                'name': output_name,
                'mime': mime_type,
                'size': img.size,
                'original': pdf_file.name
            })

        doc.close()
        return images_data

    except Exception as e:
        st.error(f"Erro ao converter PDF para imagens: {str(e)}")
        return []


# Função para combinar múltiplas imagens em um único PDF
def combine_images_to_pdf(images, dpi=None):
    try:
        pdf_bytes = io.BytesIO()

        # Lista para armazenar as imagens convertidas para bytes
        img_data_list = []

        for img_file in images:
            img = Image.open(img_file)

            # Converter para RGB se necessário
            if img.mode in ('RGBA', 'LA', 'P'):
                bg = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                bg.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = bg

            # Converter imagem para bytes
            img_bytes = io.BytesIO()
            img.save(img_bytes, format='PNG')
            img_bytes.seek(0)
            img_data_list.append(img_bytes)

        # Converter lista de imagens para PDF
        pdf_data = img2pdf.convert(*img_data_list)
        pdf_bytes.write(pdf_data)
        pdf_bytes.seek(0)

        return pdf_bytes, len(images)

    except Exception as e:
        st.error(f"Erro ao combinar imagens em PDF: {str(e)}")
        return None, 0


# Interface principal
col1, col2 = st.columns([2, 1])

with col1:
    # Upload de arquivos (agora incluindo PDF)
    uploaded_files = st.file_uploader(
        "Escolha as imagens ou PDFs para converter",
        type=['heic', 'heif', 'jpg', 'jpeg', 'png', 'webp', 'bmp', 'tiff', 'tif', 'pdf'],
        accept_multiple_files=True
    )

    if uploaded_files:
        st.success(f"{len(uploaded_files)} arquivo(s) carregado(s) com sucesso!")

        # Exibir preview das imagens (apenas para formatos de imagem, não PDF)
        image_files = [f for f in uploaded_files if not f.name.lower().endswith('.pdf')]
        if image_files and len(image_files) <= 5:
            st.subheader("📸 Pré-visualização das imagens")
            cols = st.columns(min(len(image_files), 3))
            for idx, uploaded_file in enumerate(image_files):
                with cols[idx % 3]:
                    try:
                        image = Image.open(uploaded_file)
                        st.image(image, caption=uploaded_file.name, width=150)
                    except:
                        st.write(f"⚠️ {uploaded_file.name}")

with col2:
    # Configurações de conversão
    st.subheader("⚙️ Configurações de conversão")

    # Escolher formato de saída
    output_format = st.selectbox(
        "Formato de saída",
        options=['JPG', 'PNG', 'PDF'],
        index=0  # JPG é o padrão
    )

    # Configurações específicas por formato
    if output_format == 'JPG':
        quality = st.slider("Qualidade JPG", 10, 100, 85)
    elif output_format == 'PNG':
        quality = 95  # não usado, mas mantemos um valor
    elif output_format == 'PDF':
        quality = None
        if uploaded_files and len(uploaded_files) > 1:
            st.info(f"{len(uploaded_files)} imagens serão combinadas em um único PDF.")

    # Configuração extra para conversão de PDF -> imagem (só aparece se houver PDFs carregados)
    pdf_files = [f for f in uploaded_files or [] if f.name.lower().endswith('.pdf')]
    if pdf_files and output_format in ['JPG', 'PNG']:
        dpi_pdf = st.slider("DPI para renderização do PDF", 72, 300, 150, step=1,
                            help="Maior DPI = melhor qualidade, mas arquivos maiores.")
        st.info(f"📄 {len(pdf_files)} PDF(s) serão convertidos para {output_format} (uma imagem por página).")
    elif pdf_files and output_format == 'PDF':
        st.warning(
            "⚠️ Converter PDF para PDF não faz sentido. Selecione JPG ou PNG como saída para extrair imagens do PDF.")

    # Botão de conversão
    convert_button = st.button(
        "🔄 Converter Arquivos",
        type="primary",
        disabled=not uploaded_files,
        use_container_width=True
    )

# Processar conversão
if convert_button and uploaded_files:
    st.divider()
    st.subheader("📁 Resultados da conversão")

    progress_bar = st.progress(0)
    all_results = []  # Lista de dicionários com 'data', 'name', 'mime', 'size', 'original'

    # Processar cada arquivo
    for idx, uploaded_file in enumerate(uploaded_files):
        try:
            # Atualizar progresso
            progress_bar.progress((idx + 1) / len(uploaded_files))

            # Verificar se é PDF e se a saída é imagem (JPG/PNG)
            if uploaded_file.name.lower().endswith('.pdf') and output_format in ['JPG', 'PNG']:
                # Converter PDF para várias imagens
                images_from_pdf = convert_pdf_to_images(
                    uploaded_file,
                    output_format,
                    quality=quality if output_format == 'JPG' else None,
                    dpi=dpi_pdf
                )
                all_results.extend(images_from_pdf)

            elif output_format == 'PDF' and len(uploaded_files) > 1:
                # Para múltiplas imagens e PDF como saída, combinamos em um único arquivo depois
                # Aqui apenas coletamos os arquivos de imagem (não PDF) para combinar
                # Mas vamos pular neste loop, pois o PDF combinado será tratado separadamente
                continue

            else:
                # Conversão normal de imagem (inclui PDF -> PDF? não deve acontecer, mas se tentar, ignoramos)
                if uploaded_file.name.lower().endswith('.pdf') and output_format == 'PDF':
                    st.warning(f"Conversão de PDF para PDF ignorada: {uploaded_file.name}")
                    continue

                # Converter imagem individual
                converted_file, mime_type, file_extension, img_size = convert_image(
                    uploaded_file, output_format, quality if output_format == 'JPG' else None
                )

                if converted_file:
                    # Nome do arquivo de saída
                    original_name = os.path.splitext(uploaded_file.name)[0]
                    output_filename = f"{original_name}_convertido.{file_extension}"

                    all_results.append({
                        'name': output_filename,
                        'data': converted_file,
                        'mime': mime_type,
                        'original': uploaded_file.name,
                        'size': img_size
                    })

        except Exception as e:
            st.error(f"Erro ao processar {uploaded_file.name}: {str(e)}")

    # Caso especial: múltiplas imagens para PDF
    if output_format == 'PDF' and len(uploaded_files) > 1:
        # Filtrar apenas arquivos de imagem (não PDF) para combinar
        image_files_for_pdf = [f for f in uploaded_files if not f.name.lower().endswith('.pdf')]
        if image_files_for_pdf:
            pdf_file, img_count = combine_images_to_pdf(image_files_for_pdf)

            if pdf_file:
                output_filename = "imagens_combinadas.pdf"

                st.download_button(
                    label=f"📥 Download do PDF com {img_count} imagens",
                    data=pdf_file,
                    file_name=output_filename,
                    mime="application/pdf",
                    use_container_width=True
                )
                st.success(f"✅ PDF criado com sucesso contendo {img_count} imagens!")
        else:
            st.warning("Nenhuma imagem válida para criar PDF (arquivos PDF não podem ser incluídos em PDF de saída).")

    # Exibir resultados individuais (para conversões que geraram arquivos)
    if all_results:
        st.markdown("---")

        # Exibir pré-visualização e informações de cada arquivo
        for result in all_results:
            col1, col2, col3 = st.columns([3, 2, 2])
            with col1:
                st.write(f"**{result['original']}** → {result['name']}")
                if result['size']:
                    st.caption(f"Dimensões: {result['size'][0]}x{result['size'][1]} pixels")
            with col2:
                if result['mime'].startswith('image/'):
                    try:
                        result['data'].seek(0)
                        st.image(result['data'], width=100)
                        result['data'].seek(0)  # volta ao início para uso posterior
                    except:
                        pass
            with col3:
                # Espaço reservado (não há botão individual)
                st.write("")

        # Cria o arquivo ZIP em memória
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for result in all_results:
                # Adiciona cada arquivo convertido ao ZIP
                zip_file.writestr(result['name'], result['data'].getvalue())

        zip_buffer.seek(0)

        # Botão único para download do ZIP
        st.download_button(
            label="📥 Baixar todos os arquivos (ZIP)",
            data=zip_buffer,
            file_name="converted_images.zip",
            mime="application/zip",
            use_container_width=True
        )

        st.success(f"✅ {len(all_results)} arquivo(s) gerado(s) com sucesso!")

    # Resetar barra de progresso
    progress_bar.progress(100)

# Rodapé
st.divider()
st.caption("""
🔧 **Conversor de Imagens HEIC** | Desenvolvido com Streamlit, Pillow e PyMuPDF
- Suporta conversão de HEIC/HEIF para JPG, PNG e PDF
- **Novo:** Conversão de PDF para JPG/PNG
- Mantém a qualidade durante a conversão
""")

# Instruções caso nenhum arquivo tenha sido carregado
if not uploaded_files:
    st.info("""
    👆 **Como usar:**
    1. Faça upload de uma ou mais imagens (HEIC, JPG, PNG, etc.) ou PDFs
    2. Selecione o formato de saída desejado (JPG, PNG ou PDF)
    3. Clique em "Converter Arquivos"
    4. Faça download dos arquivos convertidos
    """)

    with st.expander("💡 Quando usar este conversor?"):
        st.markdown("""
        - **Fotos do iPhone/iPad**: Dispositivos Apple frequentemente usam formato HEIC
        - **Extrair imagens de PDF**: Converta documentos PDF para JPG/PNG página a página
        - **Compactação de imagens**: Converter para JPG com qualidade ajustável
        - **Arquivos para web**: PNG para imagens com transparência
        - **Documentação**: Criar PDFs a partir de múltiplas imagens
        - **Compatibilidade**: Converter para formatos universalmente suportados
        """)