from langchain_text_splitters import RecursiveCharacterTextSplitter

def split_document(
    text: str,
    chunk_size: int=500,
    chunk_overlap: int=50
) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )
    return splitter.split_text(text)