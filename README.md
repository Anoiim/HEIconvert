# 🖼️ HEIConvert

Aplicação web multifuncional para **conversão de imagens**, **união de PDFs** e **download em massa de arquivos** a partir de planilhas do Google Sheets.

Desenvolvida com [Streamlit](https://streamlit.io/), a aplicação reúne três ferramentas em uma interface única e intuitiva.

Esta aplicação **nasceu de uma necessidade real** no ambiente de trabalho.

Na rede corporativa onde foi desenvolvida, **diversas aplicações web de conversão
e manipulação de arquivos são bloqueadas** por políticas de segurança — seja por
restrição de domínios externos, seja pela impossibilidade de enviar arquivos
sensíveis para servidores de terceiros.

Ao mesmo tempo, alguns colaboradores realizavam tarefas recorrentes que exigiam
ferramentas específicas:

- Converter fotos de iPhone (formato **HEIC**) para JPG/PNG em lotes
- **Extrair páginas de PDFs** como imagens para apresentações e relatórios
- **Unir dezenas de PDFs** assinados digitalmente em um único documento
- **Baixar em massa** arquivos hospedados em links de uma planilha interna

Ferramentas online gratuitas resolviam parcialmente o problema, mas:

- ❌ Não podiam ser acessadas dentro da rede corporativa
- ❌ Exigiam upload de documentos para servidores desconhecidos
- ❌ Não atendiam fluxos específicos (como nomear arquivos a partir da planilha)
- ❌ Tinham limites de uso ou cobrança por volume

A solução foi construir **uma aplicação local, executada no próprio ambiente**,
sem dependência de serviços externos pagos, capaz de rodar com um único comando
e acessível via navegador em `http://localhost:8501`.

O resultado é uma ferramenta **privada por design** — nenhum arquivo sai da
máquina do usuário — e **adaptada ao fluxo de trabalho real** da equipe.


---

## 📑 Índice

- [Funcionalidades](#-funcionalidades)
- [Demonstração](#-demonstração)
- [Instalação](#-instalação)
- [Como usar](#-como-usar)
- [Estrutura do projeto](#-estrutura-do-projeto)
- [Tecnologias](#-tecnologias)
- [Limitações](#-limitações)
- [Solução de problemas](#-solução-de-problemas)
- [Contribuindo](#-contribuindo)
- [Licença](#-licença)

---

## ✨ Funcionalidades

A aplicação é dividida em **três módulos independentes**, acessíveis pela barra lateral:

### 🖼️ 1. HEIConvert

Conversor de imagens com suporte a múltiplos formatos.

| Recurso | Descrição |
|---|---|
| **Entrada** | HEIC, HEIF, JPG, JPEG, PNG, WebP, BMP, TIFF, PDF |
| **Saída** | JPG, PNG, PDF |
| **Extração de PDF** | Converte cada página de um PDF em uma imagem separada |
| **Combinação de imagens** | Junta várias imagens em um único PDF |
| **Ajuste de qualidade** | Slider de qualidade para JPG (10–100) |
| **DPI configurável** | Renderização de PDF de 72 a 300 DPI |
| **Download em ZIP** | Baixa todas as conversões de uma vez |
| **Preservação de transparência** | Mantém canais alfa ao converter para PNG |

### 🔗 2. Unir PDFs

Combina múltiplos arquivos PDF em um único documento.

| Recurso | Descrição |
|---|---|
| **Limite de páginas** | Até **500 páginas** no total |
| **Limite de tamanho** | Até **500 MB** de entrada |
| **Reordenação** | Ajuste da ordem dos arquivos com botões ⬆️/⬇️ |
| **Detecção de campos** | Identifica formulários e assinaturas nos PDFs |
| **Achatar assinaturas** | Preserva a aparência visual de assinaturas digitais (opcional) |
| **Fallback robusto** | Método alternativo para PDFs corrompidos |
| **Proteção por senha** | PDFs protegidos são detectados e ignorados |
| **Validação em tempo real** | Verifica limites antes de processar |

### 📥 3. Download em Massa de Links de Planilha

Baixa arquivos em lote a partir de uma planilha do Google Sheets.

| Recurso | Descrição |
|---|---|
| **Fonte** | Google Sheets público (compartilhado como *"Qualquer pessoa com o link"*) |
| **Detecção automática** | Encontra a coluna de links por heurística |
| **Filtros dinâmicos** | Aplicação de filtros por coluna antes do download |
| **Seleção individual** | Escolha quais arquivos baixar |
| **Suporte a Google Drive** | Trata links do Drive com página de confirmação |
| **Detecção de extensão** | Por `Content-Disposition`, `Content-Type`, URL e *magic bytes* |
| **Retry automático** | 2 tentativas em caso de falha de rede |
| **Relatório CSV** | Gera relatório com sucesso/erro de cada download |
| **Download em ZIP** | Compacta todos os arquivos baixados |
| **Validação de URL** | Aceita apenas `http://` e `https://` |

---

## 🎬 Demonstração

> Em breve: GIFs demonstrando cada módulo em funcionamento.

---

## ⚙️ Instalação

### Pré-requisitos

- **Python 3.9+**
- **pip**

### Passo a passo

```bash
# 1. Clone o repositório
git clone https://github.com/seu-usuario/heiconvert.git
cd heiconvert

# 2. (Opcional) Crie um ambiente virtual
python -m venv venv
source venv/bin/activate        # Linux/macOS
venv\Scripts\activate           # Windows

# 3. Instale as dependências
pip install -r requirements.txt
