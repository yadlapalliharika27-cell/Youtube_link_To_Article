import os
from dotenv import load_dotenv
import zipfile
from functools import lru_cache

from langchain_community.document_loaders import YoutubeLoader
from langchain_groq import ChatGroq
from langchain_text_splitters import RecursiveCharacterTextSplitter

from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_core.runnables import RunnableBranch, RunnablePassthrough, RunnableLambda
from langchain_core.output_parsers import StrOutputParser


# =========================
# LOAD ENV
# =========================
load_dotenv()
os.environ['GROQ_API_KEY'] = os.getenv('groq_key')


# =========================
# LLM (GROQ)
# =========================
llm = ChatGroq(model="llama-3.1-8b-instant")


# =========================
# PROMPTS
# =========================
system_message = 'You are a Professional Article Writer specializing in Medium, LinkedIn, and tech blogs.'

human_message = """
Transform YouTube transcript into engaging professional articles.

RULES:
- Ignore intro, ads, promotions
- Focus only technical content
- Use headings, lists, code blocks
- End with summary

{transcript}
"""

summarizer_prompt = ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate.from_template(system_message),
    HumanMessagePromptTemplate.from_template(human_message)
])


# =========================
# TRANSCRIPT EXTRACTION
# =========================
@lru_cache(maxsize=10)
def extract_transcript(link: str):
    loader = YoutubeLoader.from_youtube_url(link)
    docs = loader.load()
    return docs[0].page_content


# =========================
# TEXT SPLITTING
# =========================
def get_chunks(text):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=5000,
        chunk_overlap=200
    )
    return splitter.split_text(text)


# =========================
# BASE SUMMARIZER
# =========================
base_summarizer = (
    RunnablePassthrough()
    | RunnableLambda(extract_transcript)
    | summarizer_prompt
    | llm
    | StrOutputParser()
)


# =========================
# RECURSIVE SUMMARIZER
# =========================
def recursive_summarize(text):
    chunks = get_chunks(text)
    summary = ""

    for chunk in chunks:
        prompt = f"""
Current Summary:
{summary}

New Content:
{chunk}

Update article professionally.
"""

        response = llm.invoke(prompt)
        summary = response.content

    return summary


long_summarizer = (
    RunnablePassthrough()
    | RunnableLambda(extract_transcript)
    | RunnableLambda(recursive_summarize)
)


# =========================
# LENGTH CHECK
# =========================
def is_long(link):
    text = extract_transcript(link)
    return len(text) > 1000


# =========================
# WEBPAGE GENERATOR
# =========================
web_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a frontend developer.

Generate code in format:

--html--
...
--html--

--css--
...
--css--

--js--
...
--js--
"""),
    ("human", "Create article webpage for:\n{article_content}")
])


web_chain = web_prompt | llm | StrOutputParser()


# =========================
# SMART PIPELINE
# =========================
smart_pipeline = RunnableBranch(
    (RunnableLambda(is_long), long_summarizer),
    base_summarizer
) | web_chain


# =========================
# MAIN
# =========================
def extract_section(text, tag):
    try:
        return text.split(f"--{tag}--")[1]
    except:
        return ""


def main():
    link = input("Enter YouTube URL: ")

    try:
        print("⏳ Processing...")

        result = smart_pipeline.invoke(link)

        html = extract_section(result, "html")
        css = extract_section(result, "css")
        js = extract_section(result, "js")

        with open("index.html", "w") as f:
            f.write(html)

        with open("style.css", "w") as f:
            f.write(css)

        with open("script.js", "w") as f:
            f.write(js)

        with zipfile.ZipFile("website.zip", "w") as zipf:
            zipf.write("index.html")
            zipf.write("style.css")
            zipf.write("script.js")

        print("✅ Website generated successfully!")

    except Exception as e:
        print("❌ Error:", str(e))


if __name__ == "__main__":
    main()