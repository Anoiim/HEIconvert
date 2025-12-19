import streamlit as st
import os
import io
from PIL import Image, UnidentifiedImageError
from pillow_heif import register_heif_opener
import img2pdf

# Registrar o opener para HEIC/HEIF
register_heif_opener()

# Configuração da página
st.set_page_config(
    page_title="HEIconvert",
    page_icon="🖼️",
    layout="wide"
)

# Título e descrição
st.title("🖼️ HEIConvert")
st.markdown("""
Conversor de imagens HEIC/HEIF para formatos JPG, PNG ou PDF.
Também suporta conversão entre outros formatos de imagem comuns.
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

    **Formatos de saída:**
    - JPG
    - PNG
    - PDF (para uma ou múltiplas imagens)

    **Limitações:**
    - Tamanho máximo: 200 MB
    - Para PDF: múltiplas imagens serão combinadas em um único arquivo
    """)

    st.divider()

    st.markdown("### Dicas")
    st.markdown("""
    1. Para converter múltiplas imagens para PDF, selecione várias arquivos
    2. Ajuste a qualidade JPG conforme necessário
    3. Imagens HEIC mantêm transparência ao converter para PNG
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
    # Upload de arquivos
    uploaded_files = st.file_uploader(
        "Escolha as imagens para converter",
        type=['heic', 'heif', 'jpg', 'jpeg', 'png', 'webp', 'bmp', 'tiff', 'tif'],
        accept_multiple_files=True
    )

    if uploaded_files:
        st.success(f"{len(uploaded_files)} arquivo(s) carregado(s) com sucesso!")

        # Exibir preview das imagens
        if len(uploaded_files) <= 5:  # Limitar preview para não sobrecarregar
            st.subheader("📸 Pré-visualização das imagens")
            cols = st.columns(min(len(uploaded_files), 3))
            for idx, uploaded_file in enumerate(uploaded_files):
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
        index=0
    )

    # Configurações específicas por formato
    if output_format == 'JPG':
        quality = st.slider("Qualidade JPG", 10, 100, 85)
        dpi = None
    elif output_format == 'PNG':
        quality = None
        dpi = None
    elif output_format == 'PDF':
        quality = None
        # Para PDF, podemos configurar DPI
        if len(uploaded_files) > 1:
            st.info(f"{len(uploaded_files)} imagens serão combinadas em um único PDF.")

    # Botão de conversão
    convert_button = st.button(
        "🔄 Converter Imagens",
        type="primary",
        disabled=not uploaded_files,
        use_container_width=True
    )

# Processar conversão
if convert_button and uploaded_files:
    st.divider()
    st.subheader("📁 Resultados da conversão")

    progress_bar = st.progress(0)
    results = []

    # Processar cada arquivo
    for idx, uploaded_file in enumerate(uploaded_files):
        try:
            # Atualizar progresso
            progress_bar.progress((idx + 1) / len(uploaded_files))

            # Para múltiplas imagens e PDF como saída, combinamos em um único arquivo
            if output_format == 'PDF' and len(uploaded_files) > 1:
                continue  # Vamos processar depois em bloco

            # Converter imagem individual
            converted_file, mime_type, file_extension, img_size = convert_image(
                uploaded_file, output_format, quality if output_format == 'JPG' else None
            )

            if converted_file:
                # Nome do arquivo de saída
                original_name = os.path.splitext(uploaded_file.name)[0]
                output_filename = f"{original_name}_convertido.{file_extension}"

                # Adicionar aos resultados
                results.append({
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
        pdf_file, img_count = combine_images_to_pdf(uploaded_files)

        if pdf_file:
            output_filename = "imagens_combinadas.pdf"

            # Botão de download
            st.download_button(
                label=f"📥 Download do PDF com {img_count} imagens",
                data=pdf_file,
                file_name=output_filename,
                mime="application/pdf",
                use_container_width=True
            )
            st.success(f"✅ PDF criado com sucesso contendo {img_count} imagens!")

    # Para outras conversões (individuais)
    else:
        for result in results:
            col1, col2, col3 = st.columns([3, 2, 2])

            with col1:
                st.write(f"**{result['original']}** → {output_format}")
                if result['size']:
                    st.caption(f"Tamanho: {result['size'][0]}x{result['size'][1]} pixels")

            with col2:
                # Exibir preview se for imagem
                if output_format in ['JPG', 'PNG']:
                    try:
                        # Voltar ao início do buffer para ler a imagem
                        result['data'].seek(0)
                        st.image(result['data'], width=100)
                        result['data'].seek(0)  # Voltar novamente para download
                    except:
                        pass

            with col3:
                st.download_button(
                    label="📥 Download",
                    data=result['data'],
                    file_name=result['name'],
                    mime=result['mime'],
                    key=f"download_{result['name']}",
                    use_container_width=True
                )

        if results:
            st.success(f"✅ {len(results)} arquivo(s) convertido(s) com sucesso!")

    # Resetar barra de progresso
    progress_bar.progress(100)

# Rodapé
st.divider()
st.caption("""
🔧 **Conversor de Imagens HEIC** | Desenvolvido com Streamlit e Pillow
- Suporta conversão de HEIC/HEIF para JPG, PNG e PDF
- Mantém a qualidade da imagem durante a conversão
- Interface simples e intuitiva
""")

# Instruções caso nenhum arquivo tenha sido carregado
if not uploaded_files:
    st.info("""
    👆 **Como usar:**
    1. Faça upload de uma ou mais imagens HEIC/HEIF ou outros formatos
    2. Selecione o formato de saída desejado (JPG, PNG ou PDF)
    3. Clique em "Converter Imagens"
    4. Faça download dos arquivos convertidos
    """)

    # Exemplo de áreas de uso
    with st.expander("💡 Quando usar este conversor?"):
        st.markdown("""
        - **Fotos do iPhone/iPad**: Dispositivos Apple frequentemente usam formato HEIC
        - **Compactação de imagens**: Converter para JPG com qualidade ajustável
        - **Arquivos para web**: PNG para imagens com transparência
        - **Documentação**: Criar PDFs a partir de múltiplas imagens
        - **Compatibilidade**: Converter para formatos universalmente suportados
        """)